import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.ml.predictor import predictor
from app.models.prediction import Prediction
from app.schemas.prediction import PredictionOut, ModelQuality
from app.services.bts import load_bts_csv

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["predictions"])


@router.get("/predictions/route/estimate", response_model=PredictionOut)
async def get_route_estimate(
    origin: str = Query(..., min_length=3, max_length=3),
    destination: str = Query(..., min_length=3, max_length=3),
    departure_date: datetime = Query(..., description="ISO-8601 datetime for the planned departure"),
    airline: str | None = Query(None, max_length=10),
    db: AsyncSession = Depends(get_db),
):
    """Predict expected delay for a route on a given date — no flight number required."""
    flight_dict = {
        "flight_number": None,
        "origin_iata": origin.upper(),
        "destination_iata": destination.upper(),
        "airline_code": airline.upper() if airline else None,
        "scheduled_departure": departure_date,
    }
    try:
        return await predictor.predict(flight_dict, db)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/predictions/{flight_number}", response_model=PredictionOut)
async def get_prediction(
    flight_number: str,
    origin: str = Query(...),
    destination: str = Query(...),
    scheduled_departure: datetime = Query(...),
    db: AsyncSession = Depends(get_db),
):
    flight_dict = {
        "flight_number": flight_number,
        "origin_iata": origin.upper(),
        "destination_iata": destination.upper(),
        "airline_code": flight_number[:2] if len(flight_number) >= 2 else flight_number,
        "scheduled_departure": scheduled_departure,
    }

    try:
        result = await predictor.predict(flight_dict, db)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    prediction_record = Prediction(
        flight_number=flight_number,
        origin_iata=origin.upper(),
        destination_iata=destination.upper(),
        airline_code=flight_dict["airline_code"],
        scheduled_departure=scheduled_departure,
        predicted_cancellation_probability=result.predicted_cancellation_probability,
        predicted_delay_minutes=result.predicted_delay_minutes,
        prediction_interval_low=result.prediction_interval_low,
        prediction_interval_high=result.prediction_interval_high,
        model_version=result.model_version,
        model_region=result.model_region,
        data_sources_used=result.data_sources_used.model_dump() if result.data_sources_used else None,
        fallback_used=result.fallback_used,
        fallback_reason=result.fallback_reason,
    )
    db.add(prediction_record)

    return result


@router.get("/model-metrics", response_model=ModelQuality | None)
async def get_model_metrics(db: AsyncSession = Depends(get_db)):
    """Return quality metrics for the currently active model."""
    quality = await predictor.get_model_quality(db)
    if not quality:
        raise HTTPException(status_code=404, detail="No active model metrics found")
    return quality


@router.post("/admin/reload-models")
async def reload_models(x_admin_key: str = Header(None)):
    """Hot-reload models from disk without restarting the server."""
    if x_admin_key != settings.ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin key")
    loaded = predictor.load_models()
    if loaded:
        return {"status": "ok", "version": predictor.model_version}
    raise HTTPException(status_code=500, detail="No model files found to load")


class BtsSeedRequest(BaseModel):
    filepath: str


@router.post("/seed/bts")
async def trigger_seed_bts(
    body: BtsSeedRequest,
    db: AsyncSession = Depends(get_db),
    x_admin_key: str = Header(None),
):
    if x_admin_key != settings.ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin key")
    count = await load_bts_csv(body.filepath, db)
    return {"flights_loaded": count}
