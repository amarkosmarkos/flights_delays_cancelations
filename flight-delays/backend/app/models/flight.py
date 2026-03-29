from datetime import datetime

from sqlalchemy import String, Float, DateTime, Integer, Boolean, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FlightRaw(Base):
    __tablename__ = "flights_raw"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    flight_number: Mapped[str | None] = mapped_column(String(20))
    origin_iata: Mapped[str | None] = mapped_column(String(3))
    destination_iata: Mapped[str | None] = mapped_column(String(3))
    airline_code: Mapped[str | None] = mapped_column(String(10))
    scheduled_departure: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_departure: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scheduled_arrival: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_arrival: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    departure_delay_minutes: Mapped[int | None] = mapped_column(Integer)
    arrival_delay_minutes: Mapped[int | None] = mapped_column(Integer)
    cancelled: Mapped[bool] = mapped_column(Boolean, default=False)
    cancellation_reason: Mapped[str | None] = mapped_column(String(50))
    data_source: Mapped[str | None] = mapped_column(String(50))
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("idx_flights_raw_origin", "origin_iata", "scheduled_departure"),
        Index("idx_flights_raw_route", "origin_iata", "destination_iata", "scheduled_departure"),
    )


class AirportAggregate(Base):
    __tablename__ = "airport_aggregates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    airport_iata: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_departures: Mapped[int | None] = mapped_column(Integer)
    total_arrivals: Mapped[int | None] = mapped_column(Integer)
    cancelled_departures: Mapped[int | None] = mapped_column(Integer)
    avg_departure_delay_minutes: Mapped[float | None] = mapped_column(Float)
    avg_arrival_delay_minutes: Mapped[float | None] = mapped_column(Float)
    cancellation_rate: Mapped[float | None] = mapped_column(Float)
    delay_level: Mapped[str | None] = mapped_column(String(10))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("airport_iata", "period_start", name="uq_airport_agg"),
    )


class RouteAggregate(Base):
    __tablename__ = "route_aggregates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    origin_iata: Mapped[str] = mapped_column(String(3), nullable=False)
    destination_iata: Mapped[str] = mapped_column(String(3), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_flights: Mapped[int | None] = mapped_column(Integer)
    cancelled_flights: Mapped[int | None] = mapped_column(Integer)
    avg_departure_delay_minutes: Mapped[float | None] = mapped_column(Float)
    avg_arrival_delay_minutes: Mapped[float | None] = mapped_column(Float)
    cancellation_rate: Mapped[float | None] = mapped_column(Float)
    delay_level: Mapped[str | None] = mapped_column(String(10))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("origin_iata", "destination_iata", "period_start", name="uq_route_agg"),
    )
