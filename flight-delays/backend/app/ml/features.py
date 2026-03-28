import hashlib
import math

import numpy as np


FEATURE_NAMES = [
    "hour_sin", "hour_cos",
    "day_of_week_sin", "day_of_week_cos",
    "month_sin", "month_cos",
    "route_hash",
    "airline_encoded",
    "origin_avg_delay_7d",
    "origin_cancellation_rate_7d",
    "dest_avg_delay_7d",
    "wind_speed_origin",
    "wind_speed_dest",
    "precipitation_origin",
    "precipitation_dest",
    "visibility_origin",
    "visibility_dest",
    "temperature_origin",
    "temperature_dest",
]


def _cyclic_encode(value: float, max_value: float) -> tuple[float, float]:
    angle = 2 * math.pi * value / max_value
    return math.sin(angle), math.cos(angle)


def _hash_string(s: str, modulo: int = 10000) -> int:
    return int(hashlib.md5(s.encode()).hexdigest(), 16) % modulo


def build_features(
    flight: dict,
    weather_origin: dict,
    weather_dest: dict,
    historical_stats: dict,
) -> np.ndarray:
    """Build a feature vector for ML prediction.

    Args:
        flight: dict with keys origin_iata, destination_iata, airline_code, scheduled_departure
        weather_origin: weather dict for origin airport
        weather_dest: weather dict for destination airport
        historical_stats: dict with origin/dest aggregate stats

    Returns:
        1D numpy array of features matching FEATURE_NAMES order
    """
    dep = flight.get("scheduled_departure")
    hour = dep.hour if dep else 12
    dow = dep.weekday() if dep else 0
    month = dep.month if dep else 1

    hour_sin, hour_cos = _cyclic_encode(hour, 24)
    dow_sin, dow_cos = _cyclic_encode(dow, 7)
    month_sin, month_cos = _cyclic_encode(month - 1, 12)

    route_str = f"{flight.get('origin_iata', '')}-{flight.get('destination_iata', '')}"
    route_hash = _hash_string(route_str)

    airline = flight.get("airline_code", "") or ""
    airline_encoded = _hash_string(airline, 500)

    origin_avg_delay = historical_stats.get("origin_avg_delay_7d", 0.0) or 0.0
    origin_cancel_rate = historical_stats.get("origin_cancellation_rate_7d", 0.0) or 0.0
    dest_avg_delay = historical_stats.get("dest_avg_delay_7d", 0.0) or 0.0

    features = np.array([
        hour_sin, hour_cos,
        dow_sin, dow_cos,
        month_sin, month_cos,
        route_hash,
        airline_encoded,
        origin_avg_delay,
        origin_cancel_rate,
        dest_avg_delay,
        weather_origin.get("wind_speed_kmh", 10.0),
        weather_dest.get("wind_speed_kmh", 10.0),
        weather_origin.get("precipitation_mm", 0.0),
        weather_dest.get("precipitation_mm", 0.0),
        weather_origin.get("visibility_km", 10.0),
        weather_dest.get("visibility_km", 10.0),
        weather_origin.get("temperature_celsius", 15.0),
        weather_dest.get("temperature_celsius", 15.0),
    ], dtype=np.float64)

    return features
