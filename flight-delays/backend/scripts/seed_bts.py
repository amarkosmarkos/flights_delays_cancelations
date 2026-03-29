#!/usr/bin/env python3
"""One-time script to download and seed BTS historical flight data.

Uses streaming download and chunked CSV processing to stay within
low-memory environments (e.g. Railway free tier ~512 MB RAM).
"""
import argparse
import asyncio
import os
import sys
import zipfile

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import engine, Base, async_session_factory
from app.services.bts import load_bts_csv_chunked

BTS_URL_TEMPLATE = (
    "https://transtats.bts.gov/PREZIP/"
    "On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{year}_{month}.zip"
)


async def download_and_load(year: int, month: int, data_dir: str, max_rows: int = 0) -> int:
    url = BTS_URL_TEMPLATE.format(year=year, month=month)
    zip_path = os.path.join(data_dir, f"bts_{year}_{month:02d}.zip")
    csv_path = os.path.join(data_dir, f"bts_{year}_{month:02d}.csv")

    if os.path.exists(csv_path):
        print(f"  CSV already exists: {csv_path}")
    else:
        print(f"  Downloading {url} (streaming to disk)...")
        try:
            async with httpx.AsyncClient(timeout=600.0, follow_redirects=True) as client:
                async with client.stream("GET", url) as resp:
                    resp.raise_for_status()
                    with open(zip_path, "wb") as f:
                        async for chunk in resp.aiter_bytes(chunk_size=65536):
                            f.write(chunk)

            with zipfile.ZipFile(zip_path, "r") as zf:
                csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
                if not csv_names:
                    print(f"  No CSV found in zip for {year}-{month:02d}")
                    return 0
                zf.extract(csv_names[0], data_dir)
                extracted = os.path.join(data_dir, csv_names[0])
                if extracted != csv_path:
                    os.rename(extracted, csv_path)

            os.remove(zip_path)
        except Exception as e:
            print(f"  Failed to download {year}-{month:02d}: {e}")
            for f in [zip_path, csv_path]:
                if os.path.exists(f):
                    os.remove(f)
            return 0

    async with async_session_factory() as db:
        count = await load_bts_csv_chunked(csv_path, db, max_rows=max_rows)

    if os.path.exists(csv_path):
        os.remove(csv_path)
        print(f"  Cleaned up {csv_path}")

    return count


async def main():
    parser = argparse.ArgumentParser(description="Seed BTS flight data")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--months", type=str, required=True, help="Comma-separated months, e.g. 1,2,3")
    parser.add_argument("--data-dir", type=str, default=os.environ.get("BTS_DATA_PATH", "./data/bts"))
    parser.add_argument("--max-rows", type=int, default=0, help="Max flights to load per month (0 = all)")
    args = parser.parse_args()

    months = [int(m.strip()) for m in args.months.split(",")]
    os.makedirs(args.data_dir, exist_ok=True)

    print("Creating tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    total = 0
    for month in months:
        print(f"\nProcessing {args.year}-{month:02d}...")
        count = await download_and_load(args.year, month, args.data_dir, max_rows=args.max_rows)
        total += count
        print(f"  -> {count} flights loaded")

    await engine.dispose()
    print(f"\nTotal: {total} flights loaded")


if __name__ == "__main__":
    asyncio.run(main())
