import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
from app.ml.predictor import predictor
from app.ml.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up — creating tables and loading models")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    predictor.load_models()
    start_scheduler()
    yield
    stop_scheduler()
    await engine.dispose()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Flight Delay & Cancellation API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers import airports, routes, flights, predictions

app.include_router(airports.router)
app.include_router(routes.router)
app.include_router(flights.router)
app.include_router(predictions.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
