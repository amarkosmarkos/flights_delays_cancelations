import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.airport import Airport
from app.models.flight import AirportAggregate
from app.schemas.airport import AirportLookupOut, AirportOut
from app.services.openflights import seed_airports, seed_routes

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["airports"])


@router.get("/airports", response_model=list[AirportOut])
async def get_airports(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Airport))
    airports = result.scalars().all()

    agg_result = await db.execute(
        select(AirportAggregate)
        .distinct(AirportAggregate.airport_iata)
        .order_by(AirportAggregate.airport_iata, AirportAggregate.computed_at.desc())
    )
    agg_map = {}
    for agg in agg_result.scalars().all():
        agg_map[agg.airport_iata] = agg

    out = []
    for ap in airports:
        agg = agg_map.get(ap.iata_code)
        out.append(AirportOut(
            iata=ap.iata_code,
            name=ap.name,
            lat=ap.latitude,
            lon=ap.longitude,
            city=ap.city,
            country=ap.country,
            region=ap.region,
            delay_level=agg.delay_level if agg else "UNKNOWN",
            avg_delay_minutes=agg.avg_departure_delay_minutes if agg else None,
            cancellation_rate=agg.cancellation_rate if agg else None,
            total_departures_7d=agg.total_departures if agg else None,
            data_freshness=agg.computed_at if agg else None,
        ))

    return out


@router.get("/airports/search", response_model=list[AirportLookupOut])
async def search_airports(
    q: str = Query(..., min_length=1, max_length=80),
    limit: int = Query(8, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    term = q.strip()
    if not term:
        return []

    term_up = term.upper()
    if len(term_up) == 3 and term_up.isalpha():
        exact = await db.execute(select(Airport).where(Airport.iata_code == term_up).limit(1))
        ap = exact.scalar_one_or_none()
        if ap:
            return [
                AirportLookupOut(
                    iata=ap.iata_code,
                    name=ap.name,
                    city=ap.city,
                    country=ap.country,
                    region=ap.region,
                    lat=ap.latitude,
                    lon=ap.longitude,
                )
            ]

    like = f"%{term}%"
    starts = f"{term_up}%"
    result = await db.execute(
        select(Airport)
        .where(
            or_(
                Airport.iata_code.ilike(starts),
                Airport.city.ilike(like),
                Airport.name.ilike(like),
            )
        )
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        AirportLookupOut(
            iata=ap.iata_code,
            name=ap.name,
            city=ap.city,
            country=ap.country,
            region=ap.region,
            lat=ap.latitude,
            lon=ap.longitude,
        )
        for ap in rows
    ]


@router.post("/seed/openflights")
async def trigger_seed_openflights(
    db: AsyncSession = Depends(get_db),
    x_admin_key: str = Header(None),
):
    if x_admin_key != settings.ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin key")
    airports_count = await seed_airports(db)
    routes_count = await seed_routes(db)
    return {"airports_loaded": airports_count, "routes_loaded": routes_count}
