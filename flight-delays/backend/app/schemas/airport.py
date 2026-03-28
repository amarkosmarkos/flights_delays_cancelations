from datetime import datetime

from pydantic import BaseModel


class AirportOut(BaseModel):
    iata: str
    name: str | None = None
    lat: float | None = None
    lon: float | None = None
    city: str | None = None
    country: str | None = None
    region: str | None = None
    delay_level: str | None = "UNKNOWN"
    avg_delay_minutes: float | None = None
    cancellation_rate: float | None = None
    total_departures_7d: int | None = None
    data_freshness: datetime | None = None


class AirportLookupOut(BaseModel):
    iata: str
    name: str | None = None
    city: str | None = None
    country: str | None = None
    region: str | None = None
    lat: float | None = None
    lon: float | None = None


class RouteOut(BaseModel):
    origin: str
    destination: str
    airline: str | None = None
    avg_delay_minutes: float | None = None
    estimated_delay_minutes: float | None = None
    cancellation_rate: float | None = None
    delay_level: str | None = "UNKNOWN"
    total_flights_7d: int | None = None
    reliability: str | None = "LOW"
    data_source: str | None = None
    origin_lat: float | None = None
    origin_lon: float | None = None
    dest_lat: float | None = None
    dest_lon: float | None = None
