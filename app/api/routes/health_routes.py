from fastapi import APIRouter
from app.models.schemas import HealthResponse
from app.core.config import settings

router = APIRouter()

@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
  return HealthResponse(
    status= "healthy",
    version=settings.app_version,
    platform=settings.app_name
  )