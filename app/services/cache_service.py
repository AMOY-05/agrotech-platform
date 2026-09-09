"""
Simple caching service using Redis (Upstash).
Falls back to in-memory if Redis unavailable.
"""
import json
from datetime import datetime, timedelta
from typing import Optional, Any
from loguru import logger
from app.agent.redis_memory import get_redis

# In-memory fallback cache
_memory_cache: dict = {}

# Cache TTLs
WEATHER_TTL = 1800        # 30 minutes
PRICE_TTL = 3600          # 1 hour
LOCATION_TTL = 86400      # 24 hours
YIELD_TTL = 3600          # 1 hour


def _make_key(prefix: str, *args) -> str:
    """Creates a cache key."""
    parts = [str(a).lower().strip().replace(" ", "_") for a in args]
    return f"agrotech:cache:{prefix}:{':'.join(parts)}"


async def cache_get(key: str) -> Optional[Any]:
    """Gets a value from cache."""
    redis = get_redis()

    if redis:
        try:
            data = redis.get(key)
            if data:
                parsed = json.loads(data)
                logger.info(f"Cache HIT: {key}")
                return parsed
            logger.info(f"Cache MISS: {key}")
            return None
        except Exception as e:
            logger.warning(f"Cache get failed: {e}")

    # In-memory fallback
    if key in _memory_cache:
        entry = _memory_cache[key]
        if datetime.utcnow() < entry["expires"]:
            logger.info(f"Memory cache HIT: {key}")
            return entry["data"]
        else:
            del _memory_cache[key]

    return None


async def cache_set(key: str, value: Any, ttl_seconds: int = 3600):
    """Stores a value in cache."""
    redis = get_redis()

    if redis:
        try:
            redis.setex(key, ttl_seconds, json.dumps(value))
            logger.info(f"Cache SET: {key} (TTL: {ttl_seconds}s)")
            return True
        except Exception as e:
            logger.warning(f"Cache set failed: {e}")

    # In-memory fallback
    _memory_cache[key] = {
        "data": value,
        "expires": datetime.utcnow() + timedelta(seconds=ttl_seconds)
    }
    return True


async def cache_delete(key: str):
    """Deletes a cache entry."""
    redis = get_redis()
    if redis:
        try:
            redis.delete(key)
        except Exception:
            pass
    _memory_cache.pop(key, None)


def get_weather_cache_key(region: str) -> str:
    return _make_key("weather", region)


def get_forecast_cache_key(region: str) -> str:
    return _make_key("forecast", region)


def get_price_cache_key(crop: str, region: str) -> str:
    return _make_key("price", crop, region)


def get_location_cache_key(region: str, query: str) -> str:
    return _make_key("location", region, query)