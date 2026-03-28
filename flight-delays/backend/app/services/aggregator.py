import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, case, and_, literal_column
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.airport import Airport
from app.models.flight import FlightRaw, AirportAggregate, RouteAggregate

logger = logging.getLogger(__name__)


def _compute_delay_level(avg_delay: float | None, cancel_rate: float | None) -> str:
    avg_delay = avg_delay or 0.0
    cancel_rate = cancel_rate or 0.0
    if avg_delay > 45 or cancel_rate > 0.10:
        return "SEVERE"
    if avg_delay > 25 or cancel_rate > 0.05:
        return "HIGH"
    if avg_delay > 10 or cancel_rate > 0.02:
        return "MEDIUM"
    return "LOW"


async def compute_airport_aggregates(db: AsyncSession, days: int = 7) -> None:
    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=days)
    period_end = now

    result = await db.execute(select(Airport.iata_code))
    all_iatas = [row[0] for row in result.all()]

    count = 0
    for iata in all_iatas:
        dep_stats = await db.execute(
            select(
                func.count().label("total"),
                func.sum(case((FlightRaw.cancelled == True, 1), else_=0)).label("cancelled"),
                func.avg(FlightRaw.departure_delay_minutes).label("avg_dep_delay"),
            ).where(
                FlightRaw.origin_iata == iata,
                FlightRaw.scheduled_departure >= period_start,
                FlightRaw.scheduled_departure <= period_end,
            )
        )
        dep_row = dep_stats.first()

        arr_stats = await db.execute(
            select(
                func.count().label("total"),
                func.avg(FlightRaw.arrival_delay_minutes).label("avg_arr_delay"),
            ).where(
                FlightRaw.destination_iata == iata,
                FlightRaw.scheduled_departure >= period_start,
                FlightRaw.scheduled_departure <= period_end,
            )
        )
        arr_row = arr_stats.first()

        total_dep = dep_row[0] if dep_row else 0
        if total_dep == 0:
            continue

        cancelled_dep = dep_row[1] or 0
        avg_dep_delay = float(dep_row[2]) if dep_row[2] is not None else 0.0
        total_arr = arr_row[0] if arr_row else 0
        avg_arr_delay = float(arr_row[1]) if arr_row[1] is not None else 0.0
        cancel_rate = cancelled_dep / total_dep if total_dep > 0 else 0.0
        delay_level = _compute_delay_level(avg_dep_delay, cancel_rate)

        stmt = pg_insert(AirportAggregate).values(
            airport_iata=iata,
            period_start=period_start,
            period_end=period_end,
            total_departures=total_dep,
            total_arrivals=total_arr,
            cancelled_departures=cancelled_dep,
            avg_departure_delay_minutes=round(avg_dep_delay, 2),
            avg_arrival_delay_minutes=round(avg_arr_delay, 2),
            cancellation_rate=round(cancel_rate, 4),
            delay_level=delay_level,
            computed_at=now,
        ).on_conflict_do_update(
            constraint="uq_airport_agg",
            set_={
                "period_end": period_end,
                "total_departures": total_dep,
                "total_arrivals": total_arr,
                "cancelled_departures": cancelled_dep,
                "avg_departure_delay_minutes": round(avg_dep_delay, 2),
                "avg_arrival_delay_minutes": round(avg_arr_delay, 2),
                "cancellation_rate": round(cancel_rate, 4),
                "delay_level": delay_level,
                "computed_at": now,
            },
        )
        await db.execute(stmt)
        count += 1

    await db.commit()
    logger.info("Computed airport aggregates for %d airports", count)


async def compute_route_aggregates(db: AsyncSession, days: int = 7) -> None:
    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=days)
    period_end = now

    routes_q = await db.execute(
        select(
            FlightRaw.origin_iata,
            FlightRaw.destination_iata,
        )
        .where(
            FlightRaw.scheduled_departure >= period_start,
            FlightRaw.origin_iata.is_not(None),
            FlightRaw.destination_iata.is_not(None),
        )
        .group_by(FlightRaw.origin_iata, FlightRaw.destination_iata)
    )

    count = 0
    for origin, dest in routes_q.all():
        stats = await db.execute(
            select(
                func.count().label("total"),
                func.sum(case((FlightRaw.cancelled == True, 1), else_=0)).label("cancelled"),
                func.avg(FlightRaw.departure_delay_minutes).label("avg_dep"),
                func.avg(FlightRaw.arrival_delay_minutes).label("avg_arr"),
            ).where(
                FlightRaw.origin_iata == origin,
                FlightRaw.destination_iata == dest,
                FlightRaw.scheduled_departure >= period_start,
                FlightRaw.scheduled_departure <= period_end,
            )
        )
        row = stats.first()
        total = row[0] if row else 0
        if total == 0:
            continue

        cancelled = row[1] or 0
        avg_dep = float(row[2]) if row[2] is not None else 0.0
        avg_arr = float(row[3]) if row[3] is not None else 0.0
        cancel_rate = cancelled / total if total > 0 else 0.0
        delay_level = _compute_delay_level(avg_dep, cancel_rate)

        stmt = pg_insert(RouteAggregate).values(
            origin_iata=origin,
            destination_iata=dest,
            period_start=period_start,
            period_end=period_end,
            total_flights=total,
            cancelled_flights=cancelled,
            avg_departure_delay_minutes=round(avg_dep, 2),
            avg_arrival_delay_minutes=round(avg_arr, 2),
            cancellation_rate=round(cancel_rate, 4),
            delay_level=delay_level,
            computed_at=now,
        ).on_conflict_do_update(
            constraint="uq_route_agg",
            set_={
                "period_end": period_end,
                "total_flights": total,
                "cancelled_flights": cancelled,
                "avg_departure_delay_minutes": round(avg_dep, 2),
                "avg_arrival_delay_minutes": round(avg_arr, 2),
                "cancellation_rate": round(cancel_rate, 4),
                "delay_level": delay_level,
                "computed_at": now,
            },
        )
        await db.execute(stmt)
        count += 1

    await db.commit()
    logger.info("Computed route aggregates for %d routes", count)
