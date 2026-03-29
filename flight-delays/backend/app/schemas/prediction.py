from datetime import datetime

from pydantic import BaseModel


class PredictionRequest(BaseModel):
    flight_number: str
    origin: str
    destination: str
    scheduled_departure: datetime
    airline_code: str | None = None


class DataSourcesUsed(BaseModel):
    model: str | None = None
    training_samples: int | None = None
    historical_data: str | None = None
    weather: str | None = None
    fallback: bool = False
    fallback_reason: str | None = None
    route_coverage: str | None = None
    last_retrain: str | None = None
    explanation_short: str | None = None
    explanation_full: dict | None = None


class ModelQuality(BaseModel):
    delay_dep_mae: float | None = None
    delay_dep_rmse: float | None = None
    delay_arr_mae: float | None = None
    delay_arr_rmse: float | None = None
    cancellation_auc: float | None = None
    cancellation_brier: float | None = None
    test_samples: int | None = None


class PredictionOut(BaseModel):
    flight_number: str | None = None
    origin_iata: str | None = None
    destination_iata: str | None = None
    airline_code: str | None = None
    scheduled_departure: datetime | None = None
    predicted_cancellation_probability: float | None = None
    predicted_departure_delay_minutes: float | None = None
    predicted_arrival_delay_minutes: float | None = None
    predicted_delay_minutes: float | None = None
    prediction_interval_low: float | None = None
    prediction_interval_high: float | None = None
    model_version: str | None = None
    model_region: str | None = None
    data_sources_used: DataSourcesUsed | None = None
    model_quality: ModelQuality | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None
