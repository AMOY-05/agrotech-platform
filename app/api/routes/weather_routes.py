from fastapi import APIRouter, HTTPException
from app.services.weather_service import get_current_weather, get_5day_forecast
from loguru import logger

router = APIRouter()

@router.get("/current/{region}", tags=["Weather"])
async def current_weather(region: str):
    """Get current weather for a Nigerian region. Used for testing the weather service."""
    try:
        return await get_current_weather(region)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/forecast/{region}", tags=["Weather"])
async def weather_forecast(region: str):
    """Get 5-day weather forecast for a Nigerian region."""
    try:
        return await get_5day_forecast(region)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))