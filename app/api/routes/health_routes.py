from fastapi import APIRouter
from datetime import datetime
from app.models.schemas import HealthResponse
from app.core.config import settings
from app.services.real_data_service import get_data_quality_report

router = APIRouter()

@router.get("/data-quality", tags=["System"])
async def data_quality():
    """Shows what real data sources are available."""
    return get_data_quality_report()


@router.get("/cache-stats", tags=["System"])
async def cache_stats():
    """Shows cache statistics."""
    from app.agent.redis_memory import get_redis
    redis = get_redis()

    if not redis:
        return {"redis": "not connected", "cache": "in-memory fallback"}

    try:
        # Count cached items by type
        weather_keys = redis.keys("agrotech:cache:weather:*") or []
        forecast_keys = redis.keys("agrotech:cache:forecast:*") or []
        price_keys = redis.keys("agrotech:cache:price:*") or []
        location_keys = redis.keys("agrotech:cache:location:*") or []

        return {
            "redis": "connected",
            "cached_items": {
                "weather": len(weather_keys),
                "forecasts": len(forecast_keys),
                "prices": len(price_keys),
                "locations": len(location_keys),
                "total": len(weather_keys) + len(forecast_keys) +
                         len(price_keys) + len(location_keys)
            }
        }
    except Exception as e:
        return {"redis": "error", "detail": str(e)}


@router.get("/memory-stats", tags=["System"])
async def memory_stats():
    """Shows ChromaDB vector memory statistics."""
    from app.services.vector_memory import get_memory_stats
    return get_memory_stats()

@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
  return HealthResponse(
    status= "healthy",
    version=settings.app_version,
    platform=settings.app_name
  )

@router.get("/ping", tags=["System"])
async def ping():
    """Lightweight ping endpoint for uptime monitoring."""
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}

@router.get("/ping", tags=["System"])
async def ping():
    """Lightweight ping for cron job keep-alive."""
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat()
    }