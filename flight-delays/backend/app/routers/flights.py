import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.flight import FlightRaw
from app.schemas.flight import FlightOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["flights"])


@router.get("/flights/{iata}", response_model=list[FlightOut])
async def get_flights(
    iata: str,
    direction: str = Query("departures", regex="^(departures|arrivals)$"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    iata = iata.upper()
    now = datetime.now(timezone.utc)
    window_end = now + timedelta(hours=24)

    if direction == "departures":
        stmt = (
            select(FlightRaw)
            .where(
                FlightRaw.origin_iata == iata,
                FlightRaw.scheduled_departure >= now,
                FlightRaw.scheduled_departure <= window_end,
            )
            .order_by(FlightRaw.scheduled_departure.asc())
            .limit(limit)
        )
    else:
        stmt = (
            select(FlightRaw)
            .where(
                FlightRaw.destination_iata == iata,
                FlightRaw.scheduled_arrival >= now,
                FlightRaw.scheduled_arrival <= window_end,
            )
            .order_by(FlightRaw.scheduled_arrival.asc())
            .limit(limit)
        )

    result = await db.execute(stmt)
    flights = result.scalars().all()

    return [
        FlightOut(
            id=f.id,
            flight_number=f.flight_number,
            origin_iata=f.origin_iata,
            destination_iata=f.destination_iata,
            airline_code=f.airline_code,
            scheduled_departure=f.scheduled_departure,
            actual_departure=f.actual_departure,
            scheduled_arrival=f.scheduled_arrival,
            actual_arrival=f.actual_arrival,
            departure_delay_minutes=f.departure_delay_minutes,
            arrival_delay_minutes=f.arrival_delay_minutes,
            cancelled=f.cancelled,
            cancellation_reason=f.cancellation_reason,
            data_source=f.data_source,
        )
        for f in flights
    ]
