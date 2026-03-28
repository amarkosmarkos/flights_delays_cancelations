import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.ml.predictor import predictor
from app.models.prediction import Prediction
from app.schemas.prediction import PredictionOut
from app.services.bts import load_bts_csv

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["predictions"])


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

    result = await predictor.predict(flight_dict, db)

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
