import logging
from datetime import datetime, timedelta, timezone
from collections import Counter

import httpx
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.flight import FlightRaw
from app.models.airport import Airport

logger = logging.getLogger(__name__)

TOP_100_AIRPORTS = [
    "ATL", "DFW", "DEN", "ORD", "LAX", "CLT", "LAS", "PHX", "MCO", "SEA",
    "MIA", "IAH", "JFK", "EWR", "SFO", "BOS", "MSP", "DTW", "FLL", "PHL",
    "BWI", "SLC", "DCA", "SAN", "IAD", "TPA", "MDW", "HNL", "PDX", "DAL",
    "STL", "AUS", "BNA", "RDU", "OAK", "SMF", "SNA", "MCI", "CLE", "IND",
    "FRA", "AMS", "LHR", "CDG", "MAD", "BCN", "MUC", "ZRH", "FCO", "IST",
    "VIE", "BRU", "CPH", "OSL", "HEL", "LIS", "DUB", "ATH", "WAW", "PRG",
    "DXB", "DOH", "AUH", "JED", "RUH", "BOM", "DEL", "BLR", "MAA", "HYD",
    "SIN", "HKG", "ICN", "NRT", "HND", "PEK", "PVG", "CAN", "BKK", "KUL",
    "TPE", "MNL", "CGK", "SYD", "MEL", "BNE", "AKL", "GRU", "GIG", "BOG",
    "MEX", "SCL", "LIM", "EZE", "PTY", "YYZ", "YVR", "YUL", "YYC", "ADD",
]


class OpenSkyService:
    def __init__(self):
        auth = None
        if settings.OPENSKY_USERNAME and settings.OPENSKY_PASSWORD:
            auth = (settings.OPENSKY_USERNAME, settings.OPENSKY_PASSWORD)
        self._client = httpx.AsyncClient(
            base_url=settings.OPENSKY_BASE_URL,
            auth=auth,
            timeout=30.0,
        )

    async def close(self):
        await self._client.aclose()

    async def get_airport_arrivals(self, icao: str, begin: int, end: int) -> list[dict]:
        try:
            resp = await self._client.get(
                "/flights/arrival",
                params={"airport": icao, "begin": begin, "end": end},
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning("OpenSky arrivals fetch failed for %s: %s", icao, e)
            return []

    async def get_airport_departures(self, icao: str, begin: int, end: int) -> list[dict]:
        try:
            resp = await self._client.get(
                "/flights/departure",
                params={"airport": icao, "begin": begin, "end": end},
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning("OpenSky departures fetch failed for %s: %s", icao, e)
            return []

    async def infer_scheduled_time(
        self, flight_number: str, actual_time: datetime, db: AsyncSession
    ) -> datetime | None:
        """Compute modal departure time for a flight over the last 30 days."""
        cutoff = actual_time - timedelta(days=30)
        result = await db.execute(
            select(FlightRaw.scheduled_departure)
            .where(
                FlightRaw.flight_number == flight_number,
                FlightRaw.scheduled_departure >= cutoff,
                FlightRaw.scheduled_departure.is_not(None),
            )
        )
        times = [row[0] for row in result.all()]
        if len(times) < 5:
            return None
        hour_minutes = [t.strftime("%H:%M") for t in times]
        counter = Counter(hour_minutes)
        mode_hm = counter.most_common(1)[0][0]
        hour, minute = map(int, mode_hm.split(":"))
        scheduled = actual_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if scheduled > actual_time + timedelta(hours=12):
            scheduled -= timedelta(days=1)
        return scheduled

    async def poll_top_airports(self, db: AsyncSession) -> None:
        """Poll arrivals and departures for top airports from OpenSky."""
        now = datetime.now(timezone.utc)
        end = int(now.timestamp())
        begin = int((now - timedelta(seconds=settings.POLL_INTERVAL_SECONDS)).timestamp())

        iata_to_icao = {}
        result = await db.execute(
            select(Airport.iata_code, Airport.icao_code)
            .where(Airport.iata_code.in_(TOP_100_AIRPORTS))
        )
        for row in result.all():
            if row[1]:
                iata_to_icao[row[0]] = row[1]

        for iata, icao in iata_to_icao.items():
            departures = await self.get_airport_departures(icao, begin, end)
            for dep in departures:
                callsign = (dep.get("callsign") or "").strip()
                if not callsign:
                    continue

                actual_dep_ts = dep.get("firstSeen")
                actual_arr_ts = dep.get("lastSeen")
                if not actual_dep_ts:
                    continue

                actual_dep = datetime.fromtimestamp(actual_dep_ts, tz=timezone.utc)
                actual_arr = (
                    datetime.fromtimestamp(actual_arr_ts, tz=timezone.utc)
                    if actual_arr_ts
                    else None
                )

                scheduled = await self.infer_scheduled_time(callsign, actual_dep, db)
                delay = None
                if scheduled:
                    delay = int((actual_dep - scheduled).total_seconds() / 60)

                dest_icao = dep.get("estArrivalAirport")
                dest_iata = None
                if dest_icao:
                    dest_result = await db.execute(
                        select(Airport.iata_code).where(Airport.icao_code == dest_icao)
                    )
                    dest_row = dest_result.first()
                    if dest_row:
                        dest_iata = dest_row[0]

                flight = FlightRaw(
                    flight_number=callsign,
                    origin_iata=iata,
                    destination_iata=dest_iata,
                    airline_code=callsign[:2] if len(callsign) >= 2 else callsign,
                    scheduled_departure=scheduled,
                    actual_departure=actual_dep,
                    actual_arrival=actual_arr,
                    departure_delay_minutes=delay,
                    cancelled=False,
                    data_source="OPENSKY",
                )
                db.add(flight)

            try:
                await db.commit()
            except Exception as e:
                logger.error("Failed to commit OpenSky data for %s: %s", iata, e)
                await db.rollback()

        logger.info("OpenSky poll complete — processed %d airports", len(iata_to_icao))
