from fastapi import APIRouter, HTTPException
from app.models.schemas import PriceForecastRequest, PriceForecastResponse
from app.services.price_service import forecast_crop_price
from loguru import logger
from datetime import datetime

router = APIRouter()

@router.post("/forecast", response_model=PriceForecastResponse, tags=["Price Forecast"])
async def forecast_price(request: PriceForecastRequest):
    """
    Forecast crop market prices for optimal sell timing.
    """
    logger.info(f"Price forecast: crop={request.crop_type}, region={request.region}")

    try:
        result = await forecast_crop_price(
            crop_type=request.crop_type,
            region=request.region,
            forecast_days=request.forecast_days
        )

        return PriceForecastResponse(
            success=True,
            message="Price forecast complete",
            timestamp=datetime.utcnow(),
            crop_type=result["crop_type"],
            region=result["region"],
            current_price_ngn=result["current_price_ngn"],
            forecast=result["forecast"],
            best_sell_day=result["best_sell_day"],
            trend=result["trend"]
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Price forecast failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))