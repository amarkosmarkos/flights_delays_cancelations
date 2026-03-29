from datetime import datetime

from pydantic import BaseModel


class FlightOut(BaseModel):
    id: int
    flight_number: str | None = None
    origin_iata: str | None = None
    destination_iata: str | None = None
    airline_code: str | None = None
    scheduled_departure: datetime | None = None
    actual_departure: datetime | None = None
    scheduled_arrival: datetime | None = None
    actual_arrival: datetime | None = None
    departure_delay_minutes: int | None = None
    arrival_delay_minutes: int | None = None
    cancelled: bool = False
    cancellation_reason: str | None = None
    data_source: str | None = None
