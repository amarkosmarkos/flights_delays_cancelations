import logging
from datetime import datetime
from functools import lru_cache
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_cache: dict[str, tuple[float, dict]] = {}
CACHE_TTL_SECONDS = 3600


def _cache_key(lat: float, lon: float, dt: datetime) -> str:
    return f"{lat:.2f}_{lon:.2f}_{dt.strftime('%Y%m%d%H')}"


async def get_weather_features(lat: float, lon: float, dt: datetime) -> dict[str, Any]:
    """Fetch weather features from Open-Meteo for a given location and time."""
    key = _cache_key(lat, lon, dt)

    import time
    now = time.time()
    if key in _cache:
        cached_time, cached_data = _cache[key]
        if now - cached_time < CACHE_TTL_SECONDS:
            return cached_data

    date_str = dt.strftime("%Y-%m-%d")
    hour = dt.hour

    params = {
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "hourly": "temperature_2m,wind_speed_10m,visibility,precipitation,weather_code",
        "start_date": date_str,
        "end_date": date_str,
        "timezone": "UTC",
    }

    default_features = {
        "temperature_celsius": 15.0,
        "wind_speed_kmh": 10.0,
        "visibility_km": 10.0,
        "precipitation_mm": 0.0,
        "weather_code": 0,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{settings.OPENMETEO_BASE_URL}/forecast", params=params)
            resp.raise_for_status()
            data = resp.json()

        hourly = data.get("hourly", {})
        idx = min(hour, len(hourly.get("temperature_2m", [])) - 1)
        if idx < 0:
            return default_features

        features = {
            "temperature_celsius": hourly.get("temperature_2m", [15.0])[idx],
            "wind_speed_kmh": hourly.get("wind_speed_10m", [10.0])[idx],
            "visibility_km": (hourly.get("visibility", [10000.0])[idx] or 10000.0) / 1000.0,
            "precipitation_mm": hourly.get("precipitation", [0.0])[idx] or 0.0,
            "weather_code": hourly.get("weather_code", [0])[idx] or 0,
        }

        _cache[key] = (now, features)
        return features

    except Exception as e:
        logger.warning("Open-Meteo fetch failed for (%.2f, %.2f): %s", lat, lon, e)
        return default_features
