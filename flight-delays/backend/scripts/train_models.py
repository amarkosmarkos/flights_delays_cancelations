#!/usr/bin/env python3
"""Train global XGBoost models for flight delay and cancellation prediction.

Uses all available flights in flights_raw (last 90 days, minimum 1000+ rows).

Artifacts produced in MODEL_PATH:
  - global_cancel_<version>.joblib  — calibrated XGBClassifier (or DummyClassifier)
  - global_delay_<version>.joblib   — RegressorChain(XGBRegressor) for [dep_delay, arr_delay]
  - global_features_<version>.json  — feature list snapshot

Metrics are persisted in the model_metrics table (region='GLOBAL').

Usage (local):
    python -m scripts.train_models              # uses DATABASE_URL from env / .env
    python -m scripts.train_models --db <url>

Usage (Docker Compose, from the flight-delays/ folder):
    docker compose exec backend python -m scripts.train_models
"""
import argparse
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings
from app.database import engine, Base, async_session_factory
from app.ml.trainer import ModelTrainer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("train_models")


async def main(db_url: str | None = None) -> None:
    if db_url:
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        eng = create_async_engine(db_url, echo=False)
        factory = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    else:
        eng = engine
        factory = async_session_factory

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    trainer = ModelTrainer()

    async with factory() as db:
        logger.info("Starting global model training ...")
        await trainer.retrain_all(db)

    await eng.dispose()

    model_dir = settings.MODEL_PATH
    models = [f for f in os.listdir(model_dir) if f.endswith(".joblib")] if os.path.isdir(model_dir) else []
    if models:
        logger.info("Training complete. Models saved in %s:", model_dir)
        for m in sorted(models):
            logger.info("  %s", m)
    else:
        logger.warning(
            "No models were produced — check that flights_raw has enough data (%d+ rows).",
            1000,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train global delay/cancellation XGBoost models")
    parser.add_argument("--db", type=str, default=None, help="Override DATABASE_URL")
    args = parser.parse_args()
    asyncio.run(main(args.db))
