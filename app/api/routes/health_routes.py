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

from datetime import datetime

@router.get("/ping", tags=["System"])
async def ping():
    """Lightweight ping for cron job keep-alive."""
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat()
    }