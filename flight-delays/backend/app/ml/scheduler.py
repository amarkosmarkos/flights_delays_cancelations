import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.database import async_session_factory

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def _poll_opensky():
    from app.services.opensky import OpenSkyService
    service = OpenSkyService()
    try:
        async with async_session_factory() as db:
            await service.poll_top_airports(db)
    except Exception as e:
        logger.error("OpenSky poll failed: %s", e)
    finally:
        await service.close()


async def _compute_aggregates():
    from app.services.aggregator import compute_airport_aggregates, compute_route_aggregates
    try:
        async with async_session_factory() as db:
            await compute_airport_aggregates(db)
            await compute_route_aggregates(db)
    except Exception as e:
        logger.error("Aggregate computation failed: %s", e)


async def _daily_retrain():
    from app.ml.trainer import ModelTrainer
    trainer = ModelTrainer()
    try:
        async with async_session_factory() as db:
            await trainer.retrain_all(db)
        from app.ml.predictor import predictor
        predictor.load_models()
    except Exception as e:
        logger.error("Daily retrain failed: %s", e)


async def _update_actual_delays():
    from sqlalchemy import select, and_
    from app.models.prediction import Prediction
    from app.models.flight import FlightRaw

    try:
        async with async_session_factory() as db:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=3)
            result = await db.execute(
                select(Prediction)
                .where(
                    Prediction.scheduled_departure < cutoff,
                    Prediction.actual_delay_minutes.is_(None),
                )
                .limit(500)
            )
            predictions = result.scalars().all()

            for pred in predictions:
                flight_result = await db.execute(
                    select(FlightRaw)
                    .where(
                        FlightRaw.flight_number == pred.flight_number,
                        FlightRaw.origin_iata == pred.origin_iata,
                        FlightRaw.destination_iata == pred.destination_iata,
                        FlightRaw.scheduled_departure == pred.scheduled_departure,
                    )
                    .limit(1)
                )
                flight = flight_result.scalar_one_or_none()
                if flight:
                    pred.actual_delay_minutes = flight.departure_delay_minutes
                    pred.actual_cancelled = flight.cancelled

            await db.commit()
            logger.info("Updated actual delays for %d predictions", len(predictions))
    except Exception as e:
        logger.error("Update actual delays failed: %s", e)


def start_scheduler():
    scheduler.add_job(
        _poll_opensky,
        trigger=IntervalTrigger(seconds=settings.POLL_INTERVAL_SECONDS),
        id="poll_opensky",
        replace_existing=True,
    )
    scheduler.add_job(
        _compute_aggregates,
        trigger=IntervalTrigger(seconds=settings.AGGREGATE_INTERVAL_SECONDS),
        id="compute_aggregates",
        replace_existing=True,
    )
    scheduler.add_job(
        _daily_retrain,
        trigger=CronTrigger(hour=settings.ML_RETRAIN_HOUR, minute=0),
        id="daily_retrain",
        replace_existing=True,
    )
    scheduler.add_job(
        _update_actual_delays,
        trigger=IntervalTrigger(minutes=30),
        id="update_actual_delays",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))


def stop_scheduler():
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
