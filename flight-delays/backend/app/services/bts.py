import logging
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.flight import FlightRaw

logger = logging.getLogger(__name__)

CANCELLATION_MAP = {
    "A": "CARRIER",
    "B": "WEATHER",
    "C": "NAS",
    "D": "SECURITY",
}


def _parse_hhmm(date_str: str, hhmm: int | float | str) -> datetime | None:
    """Convert BTS date + HHMM integer to a timezone-aware datetime."""
    try:
        hhmm = int(float(hhmm))
    except (ValueError, TypeError):
        return None
    if hhmm == 2400:
        hhmm = 0
    hour = hhmm // 100
    minute = hhmm % 100
    if hour > 23 or minute > 59:
        return None
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.replace(hour=hour, minute=minute, tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


COLUMN_ALIASES = {
    "FL_DATE": ["FL_DATE", "FlightDate"],
    "OP_CARRIER": ["OP_CARRIER", "Reporting_Airline", "IATA_CODE_Reporting_Airline"],
    "OP_CARRIER_FL_NUM": ["OP_CARRIER_FL_NUM", "Flight_Number_Reporting_Airline"],
    "ORIGIN": ["ORIGIN", "Origin"],
    "DEST": ["DEST", "Dest"],
    "CRS_DEP_TIME": ["CRS_DEP_TIME", "CRSDepTime"],
    "DEP_TIME": ["DEP_TIME", "DepTime"],
    "DEP_DELAY": ["DEP_DELAY", "DepDelay"],
    "CRS_ARR_TIME": ["CRS_ARR_TIME", "CRSArrTime"],
    "ARR_TIME": ["ARR_TIME", "ArrTime"],
    "ARR_DELAY": ["ARR_DELAY", "ArrDelay"],
    "CANCELLED": ["CANCELLED", "Cancelled"],
    "CANCELLATION_CODE": ["CANCELLATION_CODE", "CancellationCode"],
}


def _resolve_columns(df_columns: list[str]) -> dict[str, str]:
    """Map our canonical column names to whatever the CSV actually has."""
    col_set = set(df_columns)
    mapping = {}
    for canonical, candidates in COLUMN_ALIASES.items():
        for candidate in candidates:
            if candidate in col_set:
                mapping[canonical] = candidate
                break
    return mapping


def _process_chunk(df: pd.DataFrame, col_map: dict[str, str]) -> list[FlightRaw]:
    """Convert a DataFrame chunk into a list of FlightRaw objects."""
    c = col_map
    required = ["FL_DATE", "OP_CARRIER", "OP_CARRIER_FL_NUM", "ORIGIN", "DEST", "CRS_DEP_TIME"]
    missing = [k for k in required if k not in c]
    if missing:
        return []

    dep_delay_col = c.get("DEP_DELAY")
    arr_delay_col = c.get("ARR_DELAY")
    cancelled_col = c.get("CANCELLED")

    if dep_delay_col:
        df[dep_delay_col] = df[dep_delay_col].fillna(0)
    if arr_delay_col:
        df[arr_delay_col] = df[arr_delay_col].fillna(0)
    if cancelled_col:
        df[cancelled_col] = df[cancelled_col].fillna(0)

    flights: list[FlightRaw] = []
    for _, row in df.iterrows():
        fl_date = str(row[c["FL_DATE"]]).strip()
        carrier = str(row[c["OP_CARRIER"]]).strip()
        fl_num_raw = row[c["OP_CARRIER_FL_NUM"]]
        fl_num = str(int(float(fl_num_raw))) if pd.notna(fl_num_raw) else ""
        flight_number = f"{carrier}{fl_num}"
        origin = str(row[c["ORIGIN"]]).strip()
        dest = str(row[c["DEST"]]).strip()

        sched_dep = _parse_hhmm(fl_date, row[c["CRS_DEP_TIME"]])
        actual_dep = _parse_hhmm(fl_date, row[c["DEP_TIME"]]) if "DEP_TIME" in c else None
        sched_arr = _parse_hhmm(fl_date, row[c["CRS_ARR_TIME"]]) if "CRS_ARR_TIME" in c else None
        actual_arr = _parse_hhmm(fl_date, row[c["ARR_TIME"]]) if "ARR_TIME" in c else None

        dep_delay = int(float(row[dep_delay_col])) if dep_delay_col and pd.notna(row[dep_delay_col]) else None
        arr_delay = int(float(row[arr_delay_col])) if arr_delay_col and pd.notna(row[arr_delay_col]) else None
        cancelled = bool(int(float(row[cancelled_col]))) if cancelled_col and pd.notna(row[cancelled_col]) else False

        cancel_code_col = c.get("CANCELLATION_CODE")
        cancel_code = str(row[cancel_code_col]).strip() if cancel_code_col and pd.notna(row.get(cancel_code_col)) else ""
        cancel_reason = CANCELLATION_MAP.get(cancel_code)

        flights.append(FlightRaw(
            flight_number=flight_number,
            origin_iata=origin,
            destination_iata=dest,
            airline_code=carrier,
            scheduled_departure=sched_dep,
            actual_departure=actual_dep,
            scheduled_arrival=sched_arr,
            actual_arrival=actual_arr,
            departure_delay_minutes=dep_delay,
            arrival_delay_minutes=arr_delay,
            cancelled=cancelled,
            cancellation_reason=cancel_reason,
            data_source="BTS",
        ))

    return flights


async def load_bts_csv(filepath: str, db: AsyncSession) -> int:
    """Parse a BTS On-Time Performance CSV and bulk insert into flights_raw."""
    return await load_bts_csv_chunked(filepath, db, max_rows=0)


async def load_bts_csv_chunked(filepath: str, db: AsyncSession, max_rows: int = 0, chunk_size: int = 25_000) -> int:
    """Parse a BTS CSV in chunks to keep memory usage low."""
    logger.info("Loading BTS CSV (chunked): %s", filepath)

    try:
        reader = pd.read_csv(filepath, low_memory=False, encoding="latin-1", chunksize=chunk_size)
    except Exception as e:
        logger.error("Failed to read BTS CSV %s: %s", filepath, e)
        return 0

    col_map = None
    total = 0

    for chunk_df in reader:
        if col_map is None:
            col_map = _resolve_columns(list(chunk_df.columns))
            required = ["FL_DATE", "OP_CARRIER", "OP_CARRIER_FL_NUM", "ORIGIN", "DEST", "CRS_DEP_TIME"]
            missing = [k for k in required if k not in col_map]
            if missing:
                logger.error("BTS CSV %s missing required columns: %s", filepath, missing)
                return 0

        if max_rows > 0 and total >= max_rows:
            break

        rows_left = (max_rows - total) if max_rows > 0 else len(chunk_df)
        if rows_left < len(chunk_df):
            chunk_df = chunk_df.head(rows_left)

        flights = _process_chunk(chunk_df, col_map)
        if flights:
            db.add_all(flights)
            await db.commit()
            total += len(flights)
            logger.info("  Committed %d flights (total: %d)", len(flights), total)

    logger.info("Loaded %d flights from BTS CSV", total)
    return total
