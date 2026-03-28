import glob
import json
import logging
import os
from datetime import datetime, timezone

import joblib
import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.airport import Airport
from app.models.flight import AirportAggregate
from app.models.model_metrics import ModelMetrics
from app.ml.features import build_features
from app.services.openmeteo import get_weather_features
from app.schemas.prediction import PredictionOut, DataSourcesUsed

logger = logging.getLogger(__name__)


class FlightPredictor:
    def __init__(self):
        self.models: dict[str, dict] = {}
        self.model_versions: dict[str, str] = {}
        self.fallback_region = "US"

    def load_models(self) -> None:
        """Load the latest active model per region from MODEL_PATH."""
        if not os.path.isdir(settings.MODEL_PATH):
            logger.warning("Model path %s does not exist", settings.MODEL_PATH)
            return

        for region in ("US", "EU", "ASIA", "LATAM", "OTHER"):
            cancel_files = sorted(glob.glob(
                os.path.join(settings.MODEL_PATH, f"{region}_cancel_*.joblib")
            ))
            delay_files = sorted(glob.glob(
                os.path.join(settings.MODEL_PATH, f"{region}_delay_*.joblib")
            ))

            if not cancel_files or not delay_files:
                logger.info("No model files found for region %s", region)
                continue

            try:
                cancel_model = joblib.load(cancel_files[-1])
                delay_model = joblib.load(delay_files[-1])
                self.models[region] = {"cancel": cancel_model, "delay": delay_model}
                version = cancel_files[-1].rsplit("_", 1)[-1].replace(".joblib", "")
                self.model_versions[region] = version
                logger.info("Loaded models for region %s (version %s)", region, version)
            except Exception as e:
                logger.error("Failed to load models for region %s: %s", region, e)

    async def predict(self, flight: dict, db: AsyncSession) -> PredictionOut:
        origin_iata = flight.get("origin_iata", "")
        dest_iata = flight.get("destination_iata", "")
        region = await self._get_region(origin_iata, db)

        fallback_used = False
        fallback_reason = None
        actual_region = region

        if region not in self.models:
            fallback_used = True
            fallback_reason = (
                f"No trained model for region '{region}' yet (insufficient historical data). "
                f"Using {self.fallback_region} model as proxy."
            )
            actual_region = self.fallback_region

        if actual_region not in self.models:
            return self._no_model_response(flight, fallback_reason or "No models available")

        origin_airport = await self._get_airport(origin_iata, db)
        dest_airport = await self._get_airport(dest_iata, db)

        sched = flight.get("scheduled_departure") or datetime.now(timezone.utc)

        weather_origin = await get_weather_features(
            origin_airport.get("lat", 0), origin_airport.get("lon", 0), sched,
        )
        weather_dest = await get_weather_features(
            dest_airport.get("lat", 0), dest_airport.get("lon", 0), sched,
        )

        historical_stats = await self._get_historical_stats(origin_iata, dest_iata, db)

        features = build_features(flight, weather_origin, weather_dest, historical_stats)
        features_2d = features.reshape(1, -1)

        model_set = self.models[actual_region]

        if hasattr(model_set["cancel"], "predict_proba"):
            cancel_prob = float(model_set["cancel"].predict_proba(features_2d)[0][1])
        else:
            cancel_prob = float(model_set["cancel"].predict(features_2d)[0])

        delay_pred = float(model_set["delay"].predict(features_2d)[0])

        interval_low, interval_high = self._compute_interval(delay_pred, historical_stats)

        version = self.model_versions.get(actual_region, "unknown")
        metrics = await self._get_model_metrics(actual_region, db)
        training_samples = metrics.training_samples if metrics else 0
        last_retrain = metrics.train_date.isoformat() if metrics and metrics.train_date else None

        route_flights = historical_stats.get("route_flight_count", 0)
        if route_flights > 500:
            route_coverage = "high"
        elif route_flights > 100:
            route_coverage = "medium"
        else:
            route_coverage = "low"

        data_sources = DataSourcesUsed(
            model=f"XGBoost — {actual_region} region",
            training_samples=training_samples,
            historical_data="OpenSky Network + BTS on-time performance",
            weather="Open-Meteo forecast API",
            fallback=fallback_used,
            fallback_reason=fallback_reason,
            route_coverage=route_coverage,
            last_retrain=last_retrain,
            explanation_short=(
                f"Evaluated using {actual_region} model"
                f" · {training_samples:,} flights"
                f" · Open-Meteo weather"
                + (f" · FALLBACK from {region}" if fallback_used else "")
            ),
            explanation_full={
                "model": f"XGBoost — {actual_region} region",
                "trained": f"{last_retrain} · {training_samples:,} flights",
                "data": "OpenSky Network (inferred delays) + BTS historical",
                "weather": "Open-Meteo forecast API",
                "route": f"{route_coverage.capitalize()} coverage ({route_flights} historical flights)",
                "fallback": fallback_reason if fallback_used else None,
            },
        )

        return PredictionOut(
            flight_number=flight.get("flight_number"),
            origin_iata=origin_iata,
            destination_iata=dest_iata,
            airline_code=flight.get("airline_code"),
            scheduled_departure=sched,
            predicted_cancellation_probability=round(cancel_prob, 4),
            predicted_delay_minutes=round(delay_pred, 1),
            prediction_interval_low=round(interval_low, 1),
            prediction_interval_high=round(interval_high, 1),
            model_version=version,
            model_region=actual_region,
            data_sources_used=data_sources,
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
        )

    def _no_model_response(self, flight: dict, reason: str) -> PredictionOut:
        return PredictionOut(
            flight_number=flight.get("flight_number"),
            origin_iata=flight.get("origin_iata"),
            destination_iata=flight.get("destination_iata"),
            airline_code=flight.get("airline_code"),
            scheduled_departure=flight.get("scheduled_departure"),
            predicted_cancellation_probability=None,
            predicted_delay_minutes=None,
            prediction_interval_low=None,
            prediction_interval_high=None,
            model_version=None,
            model_region=None,
            data_sources_used=DataSourcesUsed(
                model=None,
                fallback=True,
                fallback_reason=reason,
                explanation_short=f"No prediction available: {reason}",
                explanation_full={"error": reason},
            ),
            fallback_used=True,
            fallback_reason=reason,
        )

    def _compute_interval(self, delay_pred: float, stats: dict) -> tuple[float, float]:
        std = stats.get("route_delay_std", 15.0) or 15.0
        margin = 1.5 * std
        low = delay_pred - margin
        high = delay_pred + margin
        return max(low, -30), high

    async def _get_region(self, iata: str, db: AsyncSession) -> str:
        result = await db.execute(
            select(Airport.region).where(Airport.iata_code == iata)
        )
        row = result.first()
        return row[0] if row and row[0] else "OTHER"

    async def _get_airport(self, iata: str, db: AsyncSession) -> dict:
        result = await db.execute(
            select(Airport).where(Airport.iata_code == iata)
        )
        airport = result.scalar_one_or_none()
        if airport:
            return {"lat": airport.latitude or 0, "lon": airport.longitude or 0}
        return {"lat": 0, "lon": 0}

    async def _get_historical_stats(
        self, origin_iata: str, dest_iata: str, db: AsyncSession
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

        from sqlalchemy import func
        from app.models.flight import FlightRaw
        from datetime import timedelta

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

    async def _get_model_metrics(self, region: str, db: AsyncSession) -> ModelMetrics | None:
        result = await db.execute(
            select(ModelMetrics)
            .where(ModelMetrics.region == region, ModelMetrics.is_active == True)
            .order_by(ModelMetrics.train_date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


predictor = FlightPredictor()
