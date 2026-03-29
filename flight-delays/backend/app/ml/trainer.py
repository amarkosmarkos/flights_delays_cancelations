import json
import logging
import os
import glob
from datetime import datetime, timedelta, timezone

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.dummy import DummyClassifier
from sklearn.model_selection import train_test_split
from sklearn.multioutput import RegressorChain
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    roc_auc_score,
    brier_score_loss,
)
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from xgboost import XGBClassifier, XGBRegressor

from app.config import settings
from app.models.flight import FlightRaw, AirportAggregate
from app.models.model_metrics import ModelMetrics
from app.ml.features import build_features, FEATURE_NAMES

logger = logging.getLogger(__name__)

MIN_SAMPLES_REGRESSION = 1000
MIN_SAMPLES_CLASSIFICATION = 200
TRAINING_WINDOW_DAYS = 90


class ModelTrainer:
    def __init__(self):
        os.makedirs(settings.MODEL_PATH, exist_ok=True)

    async def retrain_all(self, db: AsyncSession) -> None:
        """Train a single global model set using all available flight data."""
        await self._retrain_global(db)

    async def _retrain_global(self, db: AsyncSession) -> None:
        logger.info("Starting global model training (window=%d days)", TRAINING_WINDOW_DAYS)
        cutoff = datetime.now(timezone.utc) - timedelta(days=TRAINING_WINDOW_DAYS)

        flights_result = await db.execute(
            select(FlightRaw)
            .where(
                FlightRaw.scheduled_departure >= cutoff,
                FlightRaw.scheduled_departure.is_not(None),
            )
            .limit(500_000)
        )
        flights = flights_result.scalars().all()

        if len(flights) < MIN_SAMPLES_REGRESSION:
            logger.info(
                "Only %d flights in last %d days — falling back to all available data",
                len(flights), TRAINING_WINDOW_DAYS,
            )
            flights_result = await db.execute(
                select(FlightRaw)
                .where(FlightRaw.scheduled_departure.is_not(None))
                .limit(500_000)
            )
            flights = flights_result.scalars().all()

        if len(flights) < MIN_SAMPLES_REGRESSION:
            logger.warning(
                "Only %d flights available (need %d+), skipping training",
                len(flights),
                MIN_SAMPLES_REGRESSION,
            )
            return

        agg_cache: dict[str, dict] = {}
        agg_result = await db.execute(select(AirportAggregate))
        for agg in agg_result.scalars().all():
            agg_cache[agg.airport_iata] = {
                "origin_avg_delay_7d": agg.avg_departure_delay_minutes or 0.0,
                "origin_cancellation_rate_7d": agg.cancellation_rate or 0.0,
                "dest_avg_delay_7d": agg.avg_arrival_delay_minutes or 0.0,
            }

        X_list: list[np.ndarray] = []
        y_cancel: list[int] = []
        y_dep_delay: list[float] = []
        y_arr_delay: list[float] = []
        default_weather = {
            "wind_speed_kmh": 10.0,
            "precipitation_mm": 0.0,
            "visibility_km": 10.0,
            "temperature_celsius": 15.0,
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
                hist_stats = {**hist_stats}
                hist_stats["dest_avg_delay_7d"] = agg_cache[f.destination_iata].get(
                    "dest_avg_delay_7d", 0.0,
                )

            features = build_features(flight_dict, default_weather, default_weather, hist_stats)
            X_list.append(features)
            y_cancel.append(1 if f.cancelled else 0)
            y_dep_delay.append(
                float(f.departure_delay_minutes) if f.departure_delay_minutes is not None else 0.0,
            )
            y_arr_delay.append(
                float(f.arrival_delay_minutes) if f.arrival_delay_minutes is not None else 0.0,
            )

        X = np.array(X_list)
        y_cancel_arr = np.array(y_cancel)
        y_delay = np.column_stack([y_dep_delay, y_arr_delay])

        stratify = y_cancel_arr if len(np.unique(y_cancel_arr)) > 1 else None
        X_train, X_test, yc_train, yc_test, yd_train, yd_test = train_test_split(
            X, y_cancel_arr, y_delay, test_size=0.2, random_state=42, stratify=stratify,
        )

        # ── Classification: cancellation ──────────────────────────────────
        n_classes = len(np.unique(yc_train))
        if n_classes > 1:
            cancel_model = XGBClassifier(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.1,
                scale_pos_weight=max(1, (len(yc_train) - sum(yc_train)) / max(sum(yc_train), 1)),
                random_state=42,
                use_label_encoder=False,
                eval_metric="logloss",
            )
            cancel_model.fit(X_train, yc_train)
            calibrated = CalibratedClassifierCV(cancel_model, cv=3, method="isotonic")
            calibrated.fit(X_train, yc_train)
            cancel_model = calibrated
        else:
            logger.warning(
                "Only one class in cancellation target (class=%d). "
                "Using DummyClassifier — cancellation predictions will be constant.",
                int(yc_train[0]),
            )
            cancel_model = DummyClassifier(strategy="constant", constant=int(yc_train[0]))
            cancel_model.fit(X_train, yc_train)

        # ── Regression: multi-output (dep_delay → arr_delay) ─────────────
        # RegressorChain order=[0,1]: predicts departure delay first, then
        # arrival delay using the departure prediction as an extra feature.
        # This respects the strong dep→arr correlation.
        base_reg = XGBRegressor(
            n_estimators=200, max_depth=6, learning_rate=0.1, random_state=42,
        )
        delay_model = RegressorChain(base_reg, order=[0, 1], random_state=42)
        delay_model.fit(X_train, yd_train)

        # ── Evaluate ─────────────────────────────────────────────────────
        if hasattr(cancel_model, "predict_proba"):
            cancel_pred = cancel_model.predict_proba(X_test)[:, 1]
        else:
            cancel_pred = cancel_model.predict(X_test).astype(float)

        try:
            auc = roc_auc_score(yc_test, cancel_pred) if len(np.unique(yc_test)) > 1 else None
        except Exception:
            auc = None
        brier = brier_score_loss(yc_test, cancel_pred)

        delay_pred = delay_model.predict(X_test)
        dep_mae = mean_absolute_error(yd_test[:, 0], delay_pred[:, 0])
        dep_rmse = float(np.sqrt(mean_squared_error(yd_test[:, 0], delay_pred[:, 0])))
        arr_mae = mean_absolute_error(yd_test[:, 1], delay_pred[:, 1])
        arr_rmse = float(np.sqrt(mean_squared_error(yd_test[:, 1], delay_pred[:, 1])))

        # ── Persist ──────────────────────────────────────────────────────
        version = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")

        self._save_model(cancel_model, "cancel", version)
        self._save_model(delay_model, "delay", version)

        features_path = os.path.join(settings.MODEL_PATH, f"global_features_{version}.json")
        with open(features_path, "w") as fh:
            json.dump(FEATURE_NAMES, fh)

        await db.execute(
            update(ModelMetrics).where(ModelMetrics.is_active == True).values(is_active=False)
        )

        metrics = ModelMetrics(
            model_version=version,
            region="GLOBAL",
            training_samples=len(X_train),
            test_samples=len(X_test),
            delay_dep_mae=round(dep_mae, 3),
            delay_dep_rmse=round(dep_rmse, 3),
            delay_arr_mae=round(arr_mae, 3),
            delay_arr_rmse=round(arr_rmse, 3),
            cancellation_auc=round(auc, 4) if auc is not None else None,
            cancellation_brier=round(brier, 4),
            train_date=datetime.now(timezone.utc),
            features_used=FEATURE_NAMES,
            is_active=True,
        )
        db.add(metrics)
        await db.commit()

        self._cleanup_old_models(keep=3)
        logger.info(
            "Global model trained: %d train / %d test samples | "
            "Dep MAE=%.2f RMSE=%.2f | Arr MAE=%.2f RMSE=%.2f | "
            "AUC=%s Brier=%.4f",
            len(X_train), len(X_test),
            dep_mae, dep_rmse, arr_mae, arr_rmse,
            f"{auc:.4f}" if auc is not None else "N/A",
            brier,
        )

    def _save_model(self, model, model_type: str, version: str) -> str:
        filename = f"global_{model_type}_{version}.joblib"
        path = os.path.join(settings.MODEL_PATH, filename)
        joblib.dump(model, path)
        logger.info("Saved model: %s", path)
        return path

    def _cleanup_old_models(self, keep: int = 3) -> None:
        for model_type in ("cancel", "delay", "features"):
            ext = "joblib" if model_type != "features" else "json"
            pattern = os.path.join(settings.MODEL_PATH, f"global_{model_type}_*.{ext}")
            files = sorted(glob.glob(pattern))
            for old in files[:-keep]:
                os.remove(old)
                logger.info("Removed old model: %s", old)
