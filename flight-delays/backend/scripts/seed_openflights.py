#!/usr/bin/env python3
"""One-time script to seed airports and routes from OpenFlights data."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import engine, Base, async_session_factory
from app.services.openflights import seed_airports, seed_routes


async def main():
    print("Creating tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as db:
        print("Seeding airports from OpenFlights...")
        airports_count = await seed_airports(db)
        print(f"  -> {airports_count} airports loaded")

        print("Seeding routes from OpenFlights...")
        routes_count = await seed_routes(db)
        print(f"  -> {routes_count} routes loaded")

    await engine.dispose()
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
