from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# ``env_file=".env"`` only looks in the process cwd, so editing repo-root ``.env`` is ignored when
# uvicorn is started from ``backend/``. Load the first existing file in this search order.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE_CANDIDATES = (
    _BACKEND_DIR / ".env",
    _BACKEND_DIR.parent / ".env",
    _BACKEND_DIR.parent.parent / ".env",
)
_ENV_FILES = tuple(p for p in _ENV_FILE_CANDIDATES if p.is_file())


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/flights"
    OPENSKY_USERNAME: str = ""
    OPENSKY_PASSWORD: str = ""
    OPENMETEO_BASE_URL: str = "https://api.open-meteo.com/v1"
    OPENSKY_BASE_URL: str = "https://opensky-network.org/api"
    POLL_INTERVAL_SECONDS: int = 300
    AGGREGATE_INTERVAL_SECONDS: int = 3600
    ML_RETRAIN_HOUR: int = 2
    MODEL_PATH: str = "/app/models"
    BTS_DATA_PATH: str = "/app/data/bts"
    LOG_LEVEL: str = "INFO"
    ADMIN_KEY: str = "change-me-to-a-secure-key"

    # Globe initial routes: when False, only GLOBE_ROUTES_LIMIT random unique O-D lines are returned.
    # When True, up to GLOBE_ROUTES_SHOW_ALL_MAX (heavy for the browser).
    GLOBE_ROUTES_SHOW_ALL: bool = False
    GLOBE_ROUTES_LIMIT: int = Field(default=2800, ge=100, le=50_000)
    GLOBE_ROUTES_SHOW_ALL_MAX: int = Field(default=100_000, ge=1000, le=500_000)

    model_config = SettingsConfigDict(
        env_file=_ENV_FILES or (".env",),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
