from fastapi import APIRouter, HTTPException
from app.models.schemas import YieldPredictionRequest, YieldPredictionResponse
from app.services.yield_service import predict_yield_ml
from loguru import logger
from datetime import datetime

router = APIRouter()

@router.post("/predict", response_model=YieldPredictionResponse, tags=["Yield Prediction"])
async def predict_yield(request: YieldPredictionRequest):
    """
    Predict crop yield using trained XGBoost model.
    """
    logger.info(f"Yield prediction: crop={request.crop_type}, size={request.farm_size_hectares}ha")

    try:
        result = await predict_yield_ml(
            crop_type=request.crop_type,
            farm_size_hectares=request.farm_size_hectares,
            region=request.region,
            soil_type=request.soil_type,
            rainfall_mm=request.rainfall_mm,
            temperature_celsius=request.temperature_celsius,
            fertilizer_used=request.fertilizer_used
        )

        return YieldPredictionResponse(
            success=True,
            message="Yield prediction complete",
            timestamp=datetime.utcnow(),
            crop_type=request.crop_type,
            predicted_yield_kg=result["predicted_yield_kg"],
            confidence_interval=result["confidence_interval"],
            recommendation=result["recommendation"]
        )

    except Exception as e:
        logger.error(f"Yield prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))