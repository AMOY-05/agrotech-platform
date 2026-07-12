import joblib
import json
import numpy as np
from pathlib import Path
from loguru import logger


MODEL_DIR = Path(__file__).parent.parent / "models" / "ml"

# --- Load model + encoders once at startup ---
try:
    model = joblib.load(MODEL_DIR / "yield_model.pkl")
    encoders = joblib.load(MODEL_DIR / "yield_encoders.pkl")
    with open(MODEL_DIR / "yield_categories.json") as f:
        valid_categories = json.load(f)
    logger.info("Yield prediction model loaded successfully")
except Exception as e:
    logger.error(f"Failed to load yield model: {e}")
    model = None
    encoders = None
    valid_categories = {}


def _safe_encode(encoder, value: str, field_name: str) -> int:
    """
    Encodes a categorical value, falling back gracefully if the model
    has never seen this category before (common in production with new inputs).
    """
    value_clean = value.strip().lower().capitalize() if field_name == "region" else value.strip().lower()

    try:
        return int(encoder.transform([value_clean])[0])
    except ValueError:
        logger.warning(f"Unknown {field_name} '{value}' — model wasn't trained on this. Using closest fallback.")
        # Fallback to the most common category (index 0) rather than crashing
        return 0


async def predict_yield_ml(
    crop_type: str,
    farm_size_hectares: float,
    region: str,
    soil_type: str,
    rainfall_mm: float,
    temperature_celsius: float,
    fertilizer_used: bool
) -> dict:
    """Real ML-based yield prediction using trained XGBoost model."""
    from app.services.price_service import _normalize_crop
    from app.services.real_data_service import (
        get_real_yield_baseline,
        get_real_weather_for_region
    )
    from datetime import datetime

    crop_type = _normalize_crop(crop_type)

    if model is None:
        raise Exception("Yield prediction model not loaded")

    logger.info(
        f"Predicting yield: crop={crop_type}, "
        f"size={farm_size_hectares}ha, region={region}"
    )

    # Try to get real NASA weather if defaults are being used
    if rainfall_mm in (1200, 200):  # these are our defaults
        real_weather = get_real_weather_for_region(
            region, month=datetime.now().month
        )
        if real_weather:
            rainfall_mm = real_weather["rainfall_mm"] * 30  # daily → monthly
            temperature_celsius = real_weather["temperature_celsius"]
            logger.info(
                f"Using NASA weather: {temperature_celsius}°C, "
                f"~{rainfall_mm}mm/month for {region}"
            )

    # Get real yield baseline from FAO data
    real_baseline = get_real_yield_baseline(crop_type)
    if real_baseline:
        logger.info(
            f"Real FAO yield baseline for {crop_type}: "
            f"{real_baseline} kg/ha"
        )

    try:
        crop_encoded = _safe_encode(encoders["crop_type"], crop_type, "crop_type")
        region_encoded = _safe_encode(encoders["region"], region, "region")
        soil_encoded = _safe_encode(encoders["soil_type"], soil_type, "soil_type")

        features = np.array([[
            crop_encoded,
            farm_size_hectares,
            region_encoded,
            soil_encoded,
            rainfall_mm,
            temperature_celsius,
            int(fertilizer_used)
        ]])

        prediction = model.predict(features)[0]
        predicted_yield_per_ha = max(0, float(prediction) / farm_size_hectares)

        # If we have real FAO baseline, blend it with ML prediction
        if real_baseline:
            # Weight: 60% ML model, 40% real FAO baseline
            blended_per_ha = (predicted_yield_per_ha * 0.6 +
                             real_baseline * 0.7)
            final_yield = round(blended_per_ha * farm_size_hectares, 1)
            data_note = (
                f"Prediction blends ML model with real FAO yield data "
                f"(Nigeria avg: {real_baseline:.0f} kg/ha)"
            )
        else:
            final_yield = max(0, round(float(prediction), 1))
            data_note = "ML model prediction (no FAO baseline available for this crop)"

        margin = final_yield * 0.12
        lower_bound = round(max(0, final_yield - margin), 1)
        upper_bound = round(final_yield + margin, 1)

        recommendation = _generate_recommendation(
            crop_type, fertilizer_used, rainfall_mm, temperature_celsius
        )

        logger.info(
            f"Predicted yield: {final_yield} kg "
            f"(range: {lower_bound}-{upper_bound})"
        )

        return {
            "predicted_yield_kg": final_yield,
            "confidence_interval": {
                "lower": lower_bound,
                "upper": upper_bound
            },
            "recommendation": recommendation,
            "data_note": data_note
        }

    except Exception as e:
        logger.error(f"Yield prediction failed: {e}")
        raise Exception(f"Yield prediction error: {str(e)}")


def _generate_recommendation(crop_type: str, fertilizer_used: bool, rainfall_mm: float, temperature_celsius: float) -> str:
    """Generates a practical, rule-based recommendation alongside the ML prediction."""
    tips = []

    if not fertilizer_used:
        tips.append("Using fertilizer could significantly boost your yield — consider NPK or organic options.")

    if rainfall_mm < 800:
        tips.append("Rainfall is on the lower side for optimal growth — irrigation may help if available.")
    elif rainfall_mm > 1800:
        tips.append("High rainfall detected — ensure proper drainage to avoid waterlogging and root rot.")

    if temperature_celsius > 32:
        tips.append("Temperatures are quite high — consider shade netting or adjusting planting time.")
    elif temperature_celsius < 22:
        tips.append("Cooler temperatures may slow growth for this crop — monitor closely.")

    if not tips:
        tips.append("Conditions look favorable for good yield. Maintain current practices.")

    return " ".join(tips)