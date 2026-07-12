from fastapi import APIRouter
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