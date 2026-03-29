import csv
import io
import logging

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.airport import Airport, Route

logger = logging.getLogger(__name__)

AIRPORTS_URL = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat"
ROUTES_URL = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/routes.dat"

EU_COUNTRIES = {
    "Albania", "Armenia", "Austria", "Azerbaijan", "Belgium", "Bosnia and Herzegovina",
    "Bulgaria", "Croatia", "Cyprus", "Czech Republic", "Denmark", "Estonia",
    "Finland", "France", "Georgia", "Germany", "Greece", "Hungary", "Iceland",
    "Ireland", "Italy", "Latvia", "Lithuania", "Luxembourg", "Malta", "Moldova",
    "Monaco", "Montenegro", "Netherlands", "North Macedonia", "Norway", "Poland",
    "Portugal", "Romania", "Serbia", "Slovakia", "Slovenia", "Spain", "Sweden",
    "Switzerland", "Turkey", "Ukraine", "United Kingdom",
}

ASIA_COUNTRIES = {
    "Afghanistan", "Bangladesh", "Bhutan", "Brunei", "Cambodia", "China",
    "Hong Kong", "India", "Indonesia", "Japan", "Kazakhstan", "Kyrgyzstan",
    "Laos", "Macau", "Malaysia", "Maldives", "Mongolia", "Myanmar", "Nepal",
    "North Korea", "Pakistan", "Philippines", "Singapore", "South Korea",
    "Sri Lanka", "Taiwan", "Tajikistan", "Thailand", "Timor-Leste",
    "Turkmenistan", "Uzbekistan", "Vietnam",
}

LATAM_COUNTRIES = {
    "Argentina", "Belize", "Bolivia", "Brazil", "Chile", "Colombia",
    "Costa Rica", "Cuba", "Dominican Republic", "Ecuador", "El Salvador",
    "Guatemala", "Haiti", "Honduras", "Jamaica", "Mexico", "Nicaragua",
    "Panama", "Paraguay", "Peru", "Puerto Rico", "Trinidad and Tobago",
    "Uruguay", "Venezuela",
}

US_COUNTRIES = {"United States"}


def _classify_region(country: str) -> str:
    if country in US_COUNTRIES:
        return "US"
    if country in EU_COUNTRIES:
        return "EU"
    if country in ASIA_COUNTRIES:
        return "ASIA"
    if country in LATAM_COUNTRIES:
        return "LATAM"
    return "OTHER"


async def seed_airports(db: AsyncSession) -> int:
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(AIRPORTS_URL)
        resp.raise_for_status()

    reader = csv.reader(io.StringIO(resp.text))
    count = 0

    for row in reader:
        if len(row) < 12:
            continue
        iata = row[4].strip().strip('"')
        if not iata or iata == "\\N" or len(iata) != 3:
            continue

        icao = row[5].strip().strip('"')
        if icao == "\\N":
            icao = None

        name = row[1].strip().strip('"')
        city = row[2].strip().strip('"')
        country = row[3].strip().strip('"')
        try:
            lat = float(row[6])
            lon = float(row[7])
        except (ValueError, IndexError):
            continue

        tz = row[11].strip().strip('"') if len(row) > 11 else None
        if tz == "\\N":
            tz = None

        region = _classify_region(country)

        stmt = pg_insert(Airport).values(
            iata_code=iata,
            icao_code=icao,
            name=name,
            city=city,
            country=country,
            latitude=lat,
            longitude=lon,
            timezone=tz,
            region=region,
        ).on_conflict_do_update(
            index_elements=["iata_code"],
            set_={
                "icao_code": icao,
                "name": name,
                "city": city,
                "country": country,
                "latitude": lat,
                "longitude": lon,
                "timezone": tz,
                "region": region,
            },
        )
        await db.execute(stmt)
        count += 1

    await db.commit()
    logger.info("Seeded %d airports", count)
    return count


async def seed_routes(db: AsyncSession) -> int:
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(ROUTES_URL)
        resp.raise_for_status()

    existing = set()
    result = await db.execute(text("SELECT iata_code FROM airports"))
    for row in result.all():
        existing.add(row[0])

    reader = csv.reader(io.StringIO(resp.text))
    count = 0

    for row in reader:
        if len(row) < 7:
            continue
        airline = row[0].strip()
        origin = row[2].strip()
        dest = row[4].strip()

        if origin not in existing or dest not in existing:
            continue
        if not origin or not dest or origin == "\\N" or dest == "\\N":
            continue

        stmt = pg_insert(Route).values(
            origin_iata=origin,
            destination_iata=dest,
            airline_code=airline if airline != "\\N" else None,
        ).on_conflict_do_nothing()
        await db.execute(stmt)
        count += 1

    await db.commit()
    logger.info("Seeded %d routes", count)
    return count
