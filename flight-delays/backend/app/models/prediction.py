from datetime import datetime

from sqlalchemy import String, Float, DateTime, Integer, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    flight_number: Mapped[str | None] = mapped_column(String(20))
    origin_iata: Mapped[str | None] = mapped_column(String(3))
    destination_iata: Mapped[str | None] = mapped_column(String(3))
    airline_code: Mapped[str | None] = mapped_column(String(10))
    scheduled_departure: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    predicted_cancellation_probability: Mapped[float | None] = mapped_column(Float)
    predicted_delay_minutes: Mapped[float | None] = mapped_column(Float)
    prediction_interval_low: Mapped[float | None] = mapped_column(Float)
    prediction_interval_high: Mapped[float | None] = mapped_column(Float)
    model_version: Mapped[str | None] = mapped_column(String(50))
    model_region: Mapped[str | None] = mapped_column(String(50))
    data_sources_used: Mapped[dict | None] = mapped_column(JSON)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    fallback_reason: Mapped[str | None] = mapped_column(String(255))
    actual_delay_minutes: Mapped[int | None] = mapped_column(Integer)
    actual_cancelled: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
