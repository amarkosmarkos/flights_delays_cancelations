from datetime import datetime

from sqlalchemy import String, Float, DateTime, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Airport(Base):
    __tablename__ = "airports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    iata_code: Mapped[str] = mapped_column(String(3), unique=True, nullable=False, index=True)
    icao_code: Mapped[str | None] = mapped_column(String(4))
    name: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(100))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    timezone: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    origin_iata: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    destination_iata: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    airline_code: Mapped[str | None] = mapped_column(String(10))
    frequency_weekly: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("origin_iata", "destination_iata", "airline_code", name="uq_route"),
    )
