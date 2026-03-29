#!/bin/sh
set -e

# ── Wait for PostgreSQL to be ready ──────────────────────────────────
echo "==> Waiting for database to accept connections..."
MAX_RETRIES=30
RETRY_INTERVAL=5
for i in $(seq 1 $MAX_RETRIES); do
    if python -c "
import asyncio, sys
from app.database import engine
async def ping():
    async with engine.connect() as conn:
        await conn.execute(__import__('sqlalchemy').text('SELECT 1'))
    await engine.dispose()
asyncio.run(ping())
"; then
        echo "    Database is ready."
        break
    fi
    if [ "$i" -eq "$MAX_RETRIES" ]; then
        echo "    ERROR: Database not reachable after $MAX_RETRIES attempts. Aborting."
        exit 1
    fi
    echo "    Attempt $i/$MAX_RETRIES — database not ready, retrying in ${RETRY_INTERVAL}s..."
    sleep $RETRY_INTERVAL
done

# ── Check if seeding is needed ───────────────────────────────────────
echo "==> Checking if database needs initial seeding..."
FLIGHT_COUNT=$(python -c "
import asyncio
from app.database import engine, Base, async_session_factory
from sqlalchemy import text

async def check():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session_factory() as db:
        result = await db.execute(text('SELECT COUNT(*) FROM flights_raw'))
        count = result.scalar()
    await engine.dispose()
    print(count)

asyncio.run(check())
" 2>/dev/null || echo "0")

echo "    Found ${FLIGHT_COUNT} flights in database."

if [ "$FLIGHT_COUNT" -lt 1000 ] 2>/dev/null; then
    echo "==> Database needs seeding. Running initial data load..."

    echo "  -> Seeding airports and routes from OpenFlights..."
    python -m scripts.seed_openflights || echo "WARNING: OpenFlights seed failed."

    echo "  -> Downloading BTS flight data (2024-01, max 50000 rows)..."
    python -m scripts.seed_bts --year 2024 --months 1 --max-rows 50000 || echo "WARNING: BTS seed failed."

    echo "==> Seeding complete."
else
    echo "==> Database already seeded, skipping."
fi

# ── Train ML models ──────────────────────────────────────────────────
echo "==> Training ML models..."
python -m scripts.train_models || echo "WARNING: Model training failed. Predictions won't work until retrain."

# ── Start API server ─────────────────────────────────────────────────
echo "==> Starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
