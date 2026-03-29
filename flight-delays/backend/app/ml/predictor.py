import glob
import logging
import os
from datetime import datetime, timedelta, timezone

import joblib
import numpy as np
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.airport import Airport
from app.models.flight import AirportAggregate, FlightRaw
from app.models.model_metrics import ModelMetrics
from app.ml.features import build_features
from app.services.openmeteo import get_weather_features
from app.schemas.prediction import PredictionOut, DataSourcesUsed, ModelQuality

logger = logging.getLogger(__name__)


class FlightPredictor:
    def __init__(self):
        self.cancel_model = None
        self.delay_model = None
        self.model_version: str | None = None
        self._cached_quality: ModelQuality | None = None

    def load_models(self) -> bool:
        """Load the latest global models from MODEL_PATH. Returns True if loaded."""
        if not os.path.isdir(settings.MODEL_PATH):
            logger.warning("Model path %s does not exist", settings.MODEL_PATH)
            return False

        cancel_files = sorted(glob.glob(
            os.path.join(settings.MODEL_PATH, "global_cancel_*.joblib")
        ))
        delay_files = sorted(glob.glob(
            os.path.join(settings.MODEL_PATH, "global_delay_*.joblib")
        ))

        if not cancel_files or not delay_files:
            logger.warning("No global model files found in %s", settings.MODEL_PATH)
            return False

        try:
            self.cancel_model = joblib.load(cancel_files[-1])
            self.delay_model = joblib.load(delay_files[-1])
            self.model_version = cancel_files[-1].rsplit("_", 1)[-1].replace(".joblib", "")
            self._cached_quality = None
            logger.info("Loaded global models (version %s)", self.model_version)
            return True
        except Exception as e:
            logger.error("Failed to load global models: %s", e)
            return False

    @property
    def models_loaded(self) -> bool:
        return self.cancel_model is not None and self.delay_model is not None

    async def predict(self, flight: dict, db: AsyncSession) -> PredictionOut:
        origin_iata = flight.get("origin_iata", "")
        dest_iata = flight.get("destination_iata", "")
        sched = flight.get("scheduled_departure") or datetime.now(timezone.utc)

        if not self.models_loaded:
            raise ValueError(
                "No trained models loaded. Run `python -m scripts.train_models` first."
            )

        origin_airport = await self._get_airport(origin_iata, db)
        dest_airport = await self._get_airport(dest_iata, db)

        weather_origin = await get_weather_features(
            origin_airport.get("lat", 0), origin_airport.get("lon", 0), sched,
        )
        weather_dest = await get_weather_features(
            dest_airport.get("lat", 0), dest_airport.get("lon", 0), sched,
        )

        historical_stats = await self._get_historical_stats(origin_iata, dest_iata, db)

        features = build_features(flight, weather_origin, weather_dest, historical_stats)
        features_2d = features.reshape(1, -1)

        if hasattr(self.cancel_model, "predict_proba"):
            cancel_prob = float(self.cancel_model.predict_proba(features_2d)[0][1])
        else:
            cancel_prob = float(self.cancel_model.predict(features_2d)[0])

        delay_pred = self.delay_model.predict(features_2d)[0]
        dep_delay = float(delay_pred[0])
        arr_delay = float(delay_pred[1])

        interval_low, interval_high = self._compute_interval(dep_delay, historical_stats)

        quality = await self.get_model_quality(db)

        metrics_row = await self._get_active_metrics(db)
        training_samples = metrics_row.training_samples if metrics_row else 0
        last_retrain = metrics_row.train_date.isoformat() if metrics_row and metrics_row.train_date else None

        route_flights = historical_stats.get("route_flight_count", 0)
        route_coverage = self._coverage_label(route_flights)

        data_sources = DataSourcesUsed(
            model="XGBoost global (multi-output)",
            training_samples=training_samples,
            historical_data="BTS on-time performance",
            weather="Open-Meteo forecast API",
            fallback=False,
            fallback_reason=None,
            route_coverage=route_coverage,
            last_retrain=last_retrain,
            explanation_short=(
                f"XGBoost global · {training_samples:,} training flights · Open-Meteo weather"
            ),
            explanation_full={
                "model": "XGBoost global (RegressorChain dep→arr + calibrated classifier)",
                "trained": f"{last_retrain} · {training_samples:,} flights",
                "weather": "Open-Meteo forecast API",
                "route": f"{route_coverage} coverage ({route_flights} flights)",
            },
        )

        return PredictionOut(
            flight_number=flight.get("flight_number"),
            origin_iata=origin_iata,
            destination_iata=dest_iata,
            airline_code=flight.get("airline_code"),
            scheduled_departure=sched,
            predicted_cancellation_probability=round(cancel_prob, 4),
            predicted_departure_delay_minutes=round(dep_delay, 1),
            predicted_arrival_delay_minutes=round(arr_delay, 1),
            predicted_delay_minutes=round(dep_delay, 1),
            prediction_interval_low=round(interval_low, 1),
            prediction_interval_high=round(interval_high, 1),
            model_version=self.model_version or "unknown",
            model_region="GLOBAL",
            data_sources_used=data_sources,
            model_quality=quality,
            fallback_used=False,
            fallback_reason=None,
        )

    async def get_model_quality(self, db: AsyncSession) -> ModelQuality | None:
        if self._cached_quality is not None:
            return self._cached_quality
        row = await self._get_active_metrics(db)
        if not row:
            return None
        self._cached_quality = ModelQuality(
            delay_dep_mae=row.delay_dep_mae,
            delay_dep_rmse=row.delay_dep_rmse,
            delay_arr_mae=row.delay_arr_mae,
            delay_arr_rmse=row.delay_arr_rmse,
            cancellation_auc=row.cancellation_auc,
            cancellation_brier=row.cancellation_brier,
            test_samples=row.test_samples,
        )
        return self._cached_quality

    @staticmethod
    def _coverage_label(route_flights: int) -> str:
        if route_flights > 500:
            return "high"
        if route_flights > 100:
            return "medium"
        return "low"

    def _compute_interval(self, delay_pred: float, stats: dict) -> tuple[float, float]:
        std = stats.get("route_delay_std", 15.0) or 15.0
        margin = 1.5 * std
        return max(delay_pred - margin, -30), delay_pred + margin

    async def _get_airport(self, iata: str, db: AsyncSession) -> dict:
        result = await db.execute(
            select(Airport).where(Airport.iata_code == iata)
        )
        airport = result.scalar_one_or_none()
        if airport:
            return {"lat": airport.latitude or 0, "lon": airport.longitude or 0}
        return {"lat": 0, "lon": 0}

    async def _get_historical_stats(
        self, origin_iata: str, dest_iata: str, db: AsyncSession,
    ) -> dict:
        stats: dict = {
            "origin_avg_delay_7d": 0.0,
            "origin_cancellation_rate_7d": 0.0,
            "dest_avg_delay_7d": 0.0,
            "route_flight_count": 0,
            "route_delay_std": 15.0,
        }

        origin_agg = await db.execute(
            select(AirportAggregate)
            .where(AirportAggregate.airport_iata == origin_iata)
            .order_by(AirportAggregate.computed_at.desc())
            .limit(1)
        )
        origin_row = origin_agg.scalar_one_or_none()
        if origin_row:
            stats["origin_avg_delay_7d"] = origin_row.avg_departure_delay_minutes or 0.0
            stats["origin_cancellation_rate_7d"] = origin_row.cancellation_rate or 0.0

        dest_agg = await db.execute(
            select(AirportAggregate)
            .where(AirportAggregate.airport_iata == dest_iata)
            .order_by(AirportAggregate.computed_at.desc())
            .limit(1)
        )
        dest_row = dest_agg.scalar_one_or_none()
        if dest_row:
            stats["dest_avg_delay_7d"] = dest_row.avg_departure_delay_minutes or 0.0

        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        route_stats = await db.execute(
            select(
                func.count().label("cnt"),
                func.stddev(FlightRaw.departure_delay_minutes).label("std"),
            ).where(
                FlightRaw.origin_iata == origin_iata,
                FlightRaw.destination_iata == dest_iata,
                FlightRaw.scheduled_departure >= cutoff,
            )
        )
        route_row = route_stats.first()
        if route_row:
            stats["route_flight_count"] = route_row[0] or 0
            stats["route_delay_std"] = float(route_row[1]) if route_row[1] else 15.0

        return stats

    async def _get_active_metrics(self, db: AsyncSession) -> ModelMetrics | None:
        result = await db.execute(
            select(ModelMetrics)
            .where(ModelMetrics.is_active == True)
            .order_by(ModelMetrics.train_date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


predictor = FlightPredictor()
