import logging

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.config import settings
from app.database import get_db
from app.models.airport import Airport, Route
from app.models.flight import FlightRaw, RouteAggregate
from app.schemas.airport import RouteOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["routes"])


async def _build_airport_map(iatas: set, db: AsyncSession) -> dict:
    if not iatas:
        return {}
    result = await db.execute(select(Airport).where(Airport.iata_code.in_(list(iatas))))
    return {ap.iata_code: ap for ap in result.scalars().all()}


def _reliability_from_samples(total_flights: int | None) -> str:
    if not total_flights:
        return "LOW"
    if total_flights >= 500:
        return "HIGH"
    if total_flights >= 120:
        return "MEDIUM"
    return "LOW"


def _route_from_aggregate(agg: RouteAggregate, origin_ap: Airport, dest_ap: Airport) -> RouteOut:
    return RouteOut(
        origin=agg.origin_iata,
        destination=agg.destination_iata,
        airline=None,
        avg_delay_minutes=agg.avg_departure_delay_minutes,
        estimated_delay_minutes=agg.avg_departure_delay_minutes,
        cancellation_rate=agg.cancellation_rate,
        delay_level=agg.delay_level or "UNKNOWN",
        total_flights_7d=agg.total_flights,
        reliability=_reliability_from_samples(agg.total_flights),
        data_source="AGGREGATED_BTS_OPENSKY",
        origin_lat=origin_ap.latitude,
        origin_lon=origin_ap.longitude,
        dest_lat=dest_ap.latitude,
        dest_lon=dest_ap.longitude,
    )


def _route_from_catalog(route: Route, origin_ap: Airport, dest_ap: Airport) -> RouteOut:
    return RouteOut(
        origin=route.origin_iata,
        destination=route.destination_iata,
        airline=route.airline_code,
        avg_delay_minutes=None,
        estimated_delay_minutes=None,
        cancellation_rate=None,
        delay_level="UNKNOWN",
        total_flights_7d=None,
        reliability="LOW",
        data_source="OPENFLIGHTS_CATALOG",
        origin_lat=origin_ap.latitude,
        origin_lon=origin_ap.longitude,
        dest_lat=dest_ap.latitude,
        dest_lon=dest_ap.longitude,
    )


def _pick_best_aggregate(rows: list[RouteAggregate]) -> dict[tuple[str, str], RouteAggregate]:
    best: dict[tuple[str, str], RouteAggregate] = {}
    for agg in rows:
        key = (agg.origin_iata, agg.destination_iata)
        cur = best.get(key)
        if cur is None:
            best[key] = agg
            continue
        c_tf = cur.total_flights or 0
        n_tf = agg.total_flights or 0
        if n_tf > c_tf:
            best[key] = agg
        elif n_tf == c_tf:
            c_end = cur.period_end
            n_end = agg.period_end
            if c_end is None or (n_end is not None and n_end > c_end):
                best[key] = agg
    return best


async def _resolve_airport_candidates(term: str, db: AsyncSession, limit: int = 12) -> list[Airport]:
    q = (term or "").strip()
    if not q:
        return []
    # Accept labels like "Madrid (MAD)" from the UI datalist.
    if q.endswith(")") and "(" in q:
        maybe_iata = q.rsplit("(", 1)[1].strip(") ").upper()
        if len(maybe_iata) == 3 and maybe_iata.isalpha():
            exact = await db.execute(select(Airport).where(Airport.iata_code == maybe_iata).limit(1))
            exact_airport = exact.scalar_one_or_none()
            if exact_airport:
                return [exact_airport]
    q_up = q.upper()

    if len(q_up) == 3 and q_up.isalpha():
        exact = await db.execute(select(Airport).where(Airport.iata_code == q_up).limit(1))
        exact_airport = exact.scalar_one_or_none()
        if exact_airport:
            return [exact_airport]

    like = f"%{q}%"
    result = await db.execute(
        select(Airport)
        .where(
            or_(
                Airport.iata_code.ilike(f"{q_up}%"),
                Airport.city.ilike(like),
                Airport.name.ilike(like),
            )
        )
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/routes/popular", response_model=list[RouteOut])
async def get_popular_routes(
    db: AsyncSession = Depends(get_db),
):
    """Random global sample of catalog routes (with coordinates). When route aggregates exist in
    the database for an origin–destination pair, delay fields are filled from those aggregates only.

    Volume is controlled by ``GLOBE_ROUTES_SHOW_ALL`` and ``GLOBE_ROUTES_LIMIT`` / ``GLOBE_ROUTES_SHOW_ALL_MAX``
    in application settings (env / ``.env``).
    """
    if settings.GLOBE_ROUTES_SHOW_ALL:
        limit = settings.GLOBE_ROUTES_SHOW_ALL_MAX
        oversample_ceiling = min(200_000, max(limit * 40, 4_000))
    else:
        limit = settings.GLOBE_ROUTES_LIMIT
        oversample_ceiling = 50_000

    origin_ap = aliased(Airport)
    dest_ap = aliased(Airport)

    oversample = min(oversample_ceiling, max(limit * 40, 4_000))

    route_result = await db.execute(
        select(Route)
        .join(origin_ap, Route.origin_iata == origin_ap.iata_code)
        .join(dest_ap, Route.destination_iata == dest_ap.iata_code)
        .where(
            origin_ap.latitude.is_not(None),
            origin_ap.longitude.is_not(None),
            dest_ap.latitude.is_not(None),
            dest_ap.longitude.is_not(None),
        )
        .order_by(func.random())
        .limit(oversample)
    )
    raw_routes = route_result.scalars().all()

    picked: list[Route] = []
    seen_pairs: set[tuple[str, str]] = set()
    for route in raw_routes:
        key = (route.origin_iata, route.destination_iata)
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        picked.append(route)
        if len(picked) >= limit:
            break

    if len(picked) < limit:
        logger.warning(
            "Random route sample yielded %s unique pairs (requested %s); catalog may be small or sparse.",
            len(picked),
            limit,
        )

    if not picked:
        return []

    keys = list({(r.origin_iata, r.destination_iata) for r in picked})
    agg_result = await db.execute(
        select(RouteAggregate).where(
            tuple_(RouteAggregate.origin_iata, RouteAggregate.destination_iata).in_(keys),
            RouteAggregate.total_flights > 0,
        )
    )
    agg_by_pair = _pick_best_aggregate(list(agg_result.scalars().all()))

    iatas = {x for r in picked for x in (r.origin_iata, r.destination_iata)}
    airport_map = await _build_airport_map(iatas, db)

    out: list[RouteOut] = []
    for route in picked:
        origin = airport_map.get(route.origin_iata)
        dest = airport_map.get(route.destination_iata)
        if not origin or not dest:
            continue
        if (
            origin.latitude is None
            or origin.longitude is None
            or dest.latitude is None
            or dest.longitude is None
        ):
            continue

        agg = agg_by_pair.get((route.origin_iata, route.destination_iata))
        if agg is not None:
            out.append(_route_from_aggregate(agg, origin, dest))
        else:
            out.append(_route_from_catalog(route, origin, dest))

    return out


@router.get("/routes/search", response_model=RouteOut)
async def search_route(
    origin: str,
    destination: str,
    db: AsyncSession = Depends(get_db),
):
    """Search a route by city/airport text and return the best matching OD pair."""
    origin_candidates = await _resolve_airport_candidates(origin, db)
    dest_candidates = await _resolve_airport_candidates(destination, db)

    if not origin_candidates or not dest_candidates:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="No matching airports found for origin/destination")

    origin_iatas = [a.iata_code for a in origin_candidates]
    dest_iatas = [a.iata_code for a in dest_candidates]

    catalog_result = await db.execute(
        select(Route).where(
            and_(
                Route.origin_iata.in_(origin_iatas),
                Route.destination_iata.in_(dest_iatas),
            )
        ).limit(200)
    )
    catalog_routes = catalog_result.scalars().all()
    catalog_keys = {(r.origin_iata, r.destination_iata) for r in catalog_routes}

    # Also include pairs that exist only in operational flight data.
    raw_pairs_result = await db.execute(
        select(FlightRaw.origin_iata, FlightRaw.destination_iata)
        .where(
            FlightRaw.origin_iata.in_(origin_iatas),
            FlightRaw.destination_iata.in_(dest_iatas),
            FlightRaw.origin_iata.is_not(None),
            FlightRaw.destination_iata.is_not(None),
        )
        .group_by(FlightRaw.origin_iata, FlightRaw.destination_iata)
        .limit(300)
    )
    raw_pairs = {(row[0], row[1]) for row in raw_pairs_result.all()}

    keys = list(catalog_keys.union(raw_pairs))
    if not keys:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="No route found between the selected origin and destination")
    agg_result = await db.execute(
        select(RouteAggregate).where(
            tuple_(RouteAggregate.origin_iata, RouteAggregate.destination_iata).in_(keys),
            RouteAggregate.total_flights > 0,
        )
    )
    agg_by_pair = _pick_best_aggregate(list(agg_result.scalars().all()))

    airports = await _build_airport_map({x for k in keys for x in k}, db)

    # Prefer route with highest historical volume if available.
    best_key = None
    best_score = -1
    best_agg = None
    for key in keys:
        agg = agg_by_pair.get(key)
        score = agg.total_flights if agg and agg.total_flights else 0
        if score > best_score:
            best_score = score
            best_key = key
            best_agg = agg

    if best_key is None:
        best_key = keys[0]

    origin_ap = airports.get(best_key[0])
    dest_ap = airports.get(best_key[1])
    if not origin_ap or not dest_ap:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Route airports missing coordinates")

    if best_agg is not None:
        return _route_from_aggregate(best_agg, origin_ap, dest_ap)

    # Fallback to catalog if present, otherwise construct route from raw pair.
    catalog_route = next(
        (r for r in catalog_routes if (r.origin_iata, r.destination_iata) == best_key),
        None,
    )
    if catalog_route is not None:
        return _route_from_catalog(catalog_route, origin_ap, dest_ap)

    return RouteOut(
        origin=best_key[0],
        destination=best_key[1],
        airline=None,
        avg_delay_minutes=None,
        estimated_delay_minutes=None,
        cancellation_rate=None,
        delay_level="UNKNOWN",
        total_flights_7d=None,
        reliability="LOW",
        data_source="FLIGHTS_RAW_PAIR",
        origin_lat=origin_ap.latitude,
        origin_lon=origin_ap.longitude,
        dest_lat=dest_ap.latitude,
        dest_lon=dest_ap.longitude,
    )


@router.get("/routes/{iata}", response_model=list[RouteOut])
async def get_routes(iata: str, db: AsyncSession = Depends(get_db)):
    iata = iata.upper()

    agg_result = await db.execute(
        select(RouteAggregate)
        .where(
            or_(
                RouteAggregate.origin_iata == iata,
                RouteAggregate.destination_iata == iata,
            )
        )
        .order_by(RouteAggregate.total_flights.desc())
    )

    seen = set()
    aggregates = []
    for agg in agg_result.scalars().all():
        key = (agg.origin_iata, agg.destination_iata)
        if key not in seen:
            seen.add(key)
            aggregates.append(agg)

    all_iatas = set()
    for agg in aggregates:
        all_iatas.add(agg.origin_iata)
        all_iatas.add(agg.destination_iata)

    airport_map = await _build_airport_map(all_iatas, db)

    out = []
    for agg in aggregates:
        origin_ap = airport_map.get(agg.origin_iata)
        dest_ap = airport_map.get(agg.destination_iata)
        if not origin_ap or not dest_ap:
            continue
        if origin_ap.latitude is None or dest_ap.latitude is None:
            continue
        out.append(_route_from_aggregate(agg, origin_ap, dest_ap))
    return out
