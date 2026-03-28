import json
import logging
import os
import glob
from datetime import datetime, timedelta, timezone

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, roc_auc_score, brier_score_loss
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from xgboost import XGBClassifier, XGBRegressor

from app.config import settings
from app.models.airport import Airport
from app.models.flight import FlightRaw, AirportAggregate
from app.models.model_metrics import ModelMetrics
from app.ml.features import build_features, FEATURE_NAMES

logger = logging.getLogger(__name__)

REGIONS = ["US", "EU", "ASIA", "LATAM", "OTHER"]


class ModelTrainer:
    def __init__(self):
        os.makedirs(settings.MODEL_PATH, exist_ok=True)

    async def retrain_all(self, db: AsyncSession) -> None:
        for region in REGIONS:
            try:
                await self._retrain_region(region, db)
            except Exception as e:
                logger.error("Failed to retrain region %s: %s", region, e)

    async def _retrain_region(self, region: str, db: AsyncSession) -> None:
        logger.info("Starting retrain for region: %s", region)
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)

        airport_result = await db.execute(
            select(Airport.iata_code).where(Airport.region == region)
        )
        region_iatas = [r[0] for r in airport_result.all()]
        if not region_iatas:
            logger.info("No airports for region %s, skipping", region)
            return

        flights_result = await db.execute(
            select(FlightRaw)
            .where(
                FlightRaw.origin_iata.in_(region_iatas),
                FlightRaw.scheduled_departure >= cutoff,
                FlightRaw.scheduled_departure.is_not(None),
            )
            .limit(500_000)
        )
        flights = flights_result.scalars().all()

        if len(flights) < 1000:
            logger.info("Only %d flights for region %s (need 1000+), skipping", len(flights), region)
            return

        agg_cache = {}
        agg_result = await db.execute(
            select(AirportAggregate).where(AirportAggregate.airport_iata.in_(region_iatas))
        )
        for agg in agg_result.scalars().all():
            agg_cache[agg.airport_iata] = {
                "origin_avg_delay_7d": agg.avg_departure_delay_minutes or 0.0,
                "origin_cancellation_rate_7d": agg.cancellation_rate or 0.0,
                "dest_avg_delay_7d": agg.avg_arrival_delay_minutes or 0.0,
            }

        X_list = []
        y_cancel = []
        y_delay = []
        default_weather = {
            "wind_speed_kmh": 10.0, "precipitation_mm": 0.0,
            "visibility_km": 10.0, "temperature_celsius": 15.0,
        }

        for f in flights:
            flight_dict = {
                "origin_iata": f.origin_iata,
                "destination_iata": f.destination_iata,
                "airline_code": f.airline_code,
                "scheduled_departure": f.scheduled_departure,
            }
            hist_stats = agg_cache.get(f.origin_iata, {
                "origin_avg_delay_7d": 0.0,
                "origin_cancellation_rate_7d": 0.0,
                "dest_avg_delay_7d": 0.0,
            })
            if f.destination_iata and f.destination_iata in agg_cache:
                hist_stats["dest_avg_delay_7d"] = agg_cache[f.destination_iata].get(
                    "origin_avg_delay_7d", 0.0
                )

            features = build_features(flight_dict, default_weather, default_weather, hist_stats)
            X_list.append(features)
            y_cancel.append(1 if f.cancelled else 0)
            y_delay.append(f.departure_delay_minutes if f.departure_delay_minutes is not None else 0)

        X = np.array(X_list)
        y_cancel_arr = np.array(y_cancel)
        y_delay_arr = np.array(y_delay)

        X_train, X_test, yc_train, yc_test, yd_train, yd_test = train_test_split(
            X, y_cancel_arr, y_delay_arr, test_size=0.2, random_state=42
        )

        cancel_model = XGBClassifier(
            n_estimators=200, max_depth=6, learning_rate=0.1,
            scale_pos_weight=max(1, (len(yc_train) - sum(yc_train)) / max(sum(yc_train), 1)),
            random_state=42, use_label_encoder=False, eval_metric="logloss",
        )
        cancel_model.fit(X_train, yc_train)

        if len(np.unique(yc_train)) > 1:
            calibrated = CalibratedClassifierCV(cancel_model, cv=3, method="isotonic")
            calibrated.fit(X_train, yc_train)
            cancel_model = calibrated

        delay_model = XGBRegressor(
            n_estimators=200, max_depth=6, learning_rate=0.1, random_state=42,
        )
        delay_model.fit(X_train, yd_train)

        cancel_pred = cancel_model.predict_proba(X_test)[:, 1] if hasattr(cancel_model, "predict_proba") else cancel_model.predict(X_test)
        delay_pred = delay_model.predict(X_test)

        try:
            auc = roc_auc_score(yc_test, cancel_pred) if len(np.unique(yc_test)) > 1 else 0.5
        except Exception:
            auc = 0.5
        brier = brier_score_loss(yc_test, cancel_pred)
        mae = mean_absolute_error(yd_test, delay_pred)
        rmse = float(np.sqrt(mean_squared_error(yd_test, delay_pred)))

        version = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")

        self.save_model(cancel_model, "cancel", region, version)
        self.save_model(delay_model, "delay", region, version)

        features_path = os.path.join(settings.MODEL_PATH, f"{region}_features_{version}.json")
        with open(features_path, "w") as fh:
            json.dump(FEATURE_NAMES, fh)

        metrics = ModelMetrics(
            model_version=version,
            region=region,
            training_samples=len(X_train),
            delay_mae=round(mae, 3),
            delay_rmse=round(rmse, 3),
            cancellation_auc=round(auc, 4),
            cancellation_brier=round(brier, 4),
            train_date=datetime.now(timezone.utc),
            features_used=FEATURE_NAMES,
            is_active=True,
        )
        db.add(metrics)
        await db.commit()

        self._cleanup_old_models(region, keep=3)
        logger.info(
            "Region %s retrained: %d samples, MAE=%.2f, RMSE=%.2f, AUC=%.4f",
            region, len(X_train), mae, rmse, auc,
        )

    def save_model(self, model, model_type: str, region: str, version: str) -> str:
        filename = f"{region}_{model_type}_{version}.joblib"
        path = os.path.join(settings.MODEL_PATH, filename)
        joblib.dump(model, path)
        logger.info("Saved model: %s", path)
        return path

    def _cleanup_old_models(self, region: str, keep: int = 3) -> None:
        for model_type in ("cancel", "delay", "features"):
            ext = "joblib" if model_type != "features" else "json"
            pattern = os.path.join(settings.MODEL_PATH, f"{region}_{model_type}_*.{ext}")
            files = sorted(glob.glob(pattern))
            for old in files[:-keep]:
                os.remove(old)
                logger.info("Removed old model: %s", old)

    def _get_region_for_route(self, origin_iata: str, dest_iata: str) -> str:
        return "US"
