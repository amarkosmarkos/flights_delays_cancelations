#!/usr/bin/env python3
"""One-time script to download and seed BTS historical flight data."""
import argparse
import asyncio
import io
import os
import sys
import zipfile

import httpx
from tqdm import tqdm

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import engine, Base, async_session_factory
from app.services.bts import load_bts_csv

BTS_URL_TEMPLATE = (
    "https://transtats.bts.gov/PREZIP/"
    "On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{year}_{month}.zip"
)


async def download_and_load(year: int, month: int, data_dir: str) -> int:
    url = BTS_URL_TEMPLATE.format(year=year, month=month)
    zip_path = os.path.join(data_dir, f"bts_{year}_{month:02d}.zip")
    csv_path = os.path.join(data_dir, f"bts_{year}_{month:02d}.csv")

    if os.path.exists(csv_path):
        print(f"  CSV already exists: {csv_path}")
    else:
        print(f"  Downloading {url}...")
        try:
            async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()

            with open(zip_path, "wb") as f:
                f.write(resp.content)

            with zipfile.ZipFile(zip_path, "r") as zf:
                csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
                if not csv_names:
                    print(f"  No CSV found in zip for {year}-{month:02d}")
                    return 0
                with open(csv_path, "wb") as out:
                    out.write(zf.read(csv_names[0]))

            os.remove(zip_path)
        except Exception as e:
            print(f"  Failed to download {year}-{month:02d}: {e}")
            return 0

    async with async_session_factory() as db:
        count = await load_bts_csv(csv_path, db)

    return count


async def main():
    parser = argparse.ArgumentParser(description="Seed BTS flight data")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--months", type=str, required=True, help="Comma-separated months, e.g. 1,2,3")
    parser.add_argument("--data-dir", type=str, default=os.environ.get("BTS_DATA_PATH", "./data/bts"))
    args = parser.parse_args()

    months = [int(m.strip()) for m in args.months.split(",")]
    os.makedirs(args.data_dir, exist_ok=True)

    print("Creating tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    total = 0
    for month in tqdm(months, desc="BTS months"):
        print(f"\nProcessing {args.year}-{month:02d}...")
        count = await download_and_load(args.year, month, args.data_dir)
        total += count
        print(f"  -> {count} flights loaded")

    await engine.dispose()
    print(f"\nTotal: {total} flights loaded")


if __name__ == "__main__":
    asyncio.run(main())
