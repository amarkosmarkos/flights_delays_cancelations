from datetime import datetime

from sqlalchemy import String, Float, DateTime, Integer, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ModelMetrics(Base):
    __tablename__ = "model_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_version: Mapped[str | None] = mapped_column(String(50))
    region: Mapped[str | None] = mapped_column(String(50))
    training_samples: Mapped[int | None] = mapped_column(Integer)
    test_samples: Mapped[int | None] = mapped_column(Integer)
    delay_dep_mae: Mapped[float | None] = mapped_column(Float)
    delay_dep_rmse: Mapped[float | None] = mapped_column(Float)
    delay_arr_mae: Mapped[float | None] = mapped_column(Float)
    delay_arr_rmse: Mapped[float | None] = mapped_column(Float)
    cancellation_auc: Mapped[float | None] = mapped_column(Float)
    cancellation_brier: Mapped[float | None] = mapped_column(Float)
    train_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    features_used: Mapped[dict | None] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
