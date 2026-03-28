# Flight Delays & Cancellations — Setup Guide

## Environment Variables

Create `.env` in the workspace root from `.env.example` and fill in your values:

```bash
cp .env.example .env
```

| Variable | Description | Required |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string (asyncpg) | Yes |
| `OPENSKY_USERNAME` | OpenSky Network credentials (optional, increases rate limits) | No |
| `OPENSKY_PASSWORD` | OpenSky Network password | No |
| `ADMIN_KEY` | Secret key for admin endpoints (seed triggers) | Yes |
| `VITE_API_URL` | Frontend API base URL (empty for same-origin in production) | No |

---

## Local Development with Docker Compose

```bash
cd flight-delays

# Start all services (postgres + backend + frontend)
docker compose up --build

# Services will be available at:
#   Frontend: http://localhost:3001
#   Backend:  http://localhost:8001
#   API docs: http://localhost:8001/docs
```

### Seed Data

After the services are running, seed the database with airport and route data:

```bash
# Option A: Via the API (requires ADMIN_KEY)
curl -X POST http://localhost:8000/api/seed/openflights \
  -H "X-Admin-Key: change-me-to-a-secure-key"

# Option B: Run the script directly
docker compose exec backend python scripts/seed_openflights.py
```

To load BTS historical flight data (US domestic flights):

```bash
# Downloads and loads BTS data for the specified year/months
docker compose exec backend python scripts/seed_bts.py --year 2023 --months 1,2,3

# Or load a local CSV via the API
curl -X POST http://localhost:8000/api/seed/bts \
  -H "X-Admin-Key: change-me-to-a-secure-key" \
  -H "Content-Type: application/json" \
  -d '{"filepath": "/app/data/bts/On_Time_2023_01.csv"}'
```

After seeding, the aggregation scheduler will compute 7-day rolling stats within the hour, or trigger it manually:

```bash
docker compose exec backend python -c "
import asyncio
from app.database import async_session_factory
from app.services.aggregator import compute_airport_aggregates, compute_route_aggregates
async def run():
    async with async_session_factory() as db:
        await compute_airport_aggregates(db)
        await compute_route_aggregates(db)
asyncio.run(run())
"
```

---

## Railway Deployment

### Backend

1. Create a new project on [Railway](https://railway.app)
2. Add a **PostgreSQL** plugin (Railway provisions it automatically)
3. Create a new service from your repo, set the root directory to `backend/`
4. Set environment variables in the Railway dashboard:
   - `DATABASE_URL` — Railway provides this via the Postgres plugin reference (`${{Postgres.DATABASE_URL}}`, replace `postgresql://` with `postgresql+asyncpg://`)
   - `ADMIN_KEY` — your secret admin key
   - `MODEL_PATH` — `/app/models`
5. Deploy. The health check at `/health` will confirm the service is running.

### Frontend

1. Create another service in the same project, root directory `frontend/`
2. Set `VITE_API_URL` to the backend's Railway public URL (e.g., `https://your-backend.up.railway.app`)
3. Update `nginx.conf` proxy_pass to point to the backend's internal Railway hostname if using private networking.
4. Deploy.

---

## Architecture Overview

```
[Browser] → [Frontend (React + Globe.gl)]
                ↓ /api/*
          [Backend (FastAPI)]
                ↓
          [PostgreSQL]
                ↓
    ┌──────────────────────────┐
    │   Scheduler (APScheduler) │
    │                          │
    │  • OpenSky poll (5 min)  │
    │  • Aggregates (1 hour)   │
    │  • ML retrain (daily)    │
    │  • Update actuals (30m)  │
    └──────────────────────────┘
```

### Data Flow

1. **Seed**: OpenFlights airports/routes + BTS historical CSVs populate the database
2. **Poll**: Every 5 minutes, OpenSky Network is queried for the 100 busiest airports
3. **Aggregate**: Every hour, 7-day rolling stats are computed per airport and route
4. **Train**: Daily at 02:00 UTC, XGBoost models retrain per region (US, EU, ASIA, LATAM, OTHER)
5. **Predict**: On-demand via `/api/predictions/{flight_number}` — returns probability + provenance

### ML Models

- **Cancellation**: XGBoost classifier, calibrated with isotonic regression
- **Delay**: XGBoost regressor
- **Features**: Time cyclical encoding, route/airline hashes, 7-day aggregate stats, Open-Meteo weather
- **Regions**: Separate models per region; fallback to US model when insufficient training data
- **Versioning**: Models saved as `{REGION}_{type}_{YYYYMMDD_HHMM}.joblib`, last 3 kept per region
