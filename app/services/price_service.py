"""
Price forecasting service.
Uses real WFP market data as primary source,
falls back to seasonal model if real data unavailable.
"""
import numpy as np
from datetime import datetime, timedelta
from loguru import logger
from typing import Optional

# Import real data service
from app.services.real_data_service import get_real_price_forecast

# Fallback synthetic data (kept for crops not in WFP dataset)
SEASONAL_PATTERN = {
    1: 1.15, 2: 1.20, 3: 1.10, 4: 0.95, 5: 0.90,
    6: 0.88, 7: 0.92, 8: 0.95, 9: 1.00, 10: 0.85,
    11: 0.88, 12: 1.10
}

ANNUAL_INFLATION = 0.15
BASE_DATE = datetime(2024, 1, 1)

# Fallback prices for crops not in WFP data
FALLBACK_BASE_PRICES = {
    "tomato":   {"lagos": 800,  "kano": 600,  "oyo": 700,
                 "rivers": 900, "kaduna": 650},
    "maize":    {"lagos": 450,  "kano": 380,  "oyo": 420,
                 "rivers": 480, "kaduna": 400},
    "cassava":  {"lagos": 200,  "kano": 180,  "oyo": 190,
                 "rivers": 220, "kaduna": 185},
    "rice":     {"lagos": 950,  "kano": 880,  "oyo": 920,
                 "rivers": 980, "kaduna": 900},
    "yam":      {"lagos": 600,  "kano": 500,  "oyo": 550,
                 "rivers": 650, "kaduna": 520},
    "pepper":   {"lagos": 1200, "kano": 1000, "oyo": 1100,
                 "rivers": 1300, "kaduna": 1050},
    "cowpea":   {"lagos": 700,  "kano": 580,  "oyo": 650,
                 "rivers": 750, "kaduna": 600},
    "plantain": {"lagos": 400,  "kano": 350,  "oyo": 380,
                 "rivers": 450, "kaduna": 360},
}

CROP_ALIASES = {
    "tomatoes": "tomato",
    "maize corn": "maize",
    "corn": "maize",
    "cassavas": "cassava",
    "yams": "yam",
    "peppers": "pepper",
    "chili": "pepper",
    "chilli": "pepper",
    "cowpeas": "cowpea",
    "plantains": "plantain",
    "bananas": "plantain",
}


def _normalize_crop(crop_type: str) -> str:
    """Normalizes crop name."""
    cleaned = crop_type.lower().strip().rstrip("s")
    direct = crop_type.lower().strip()
    if direct in CROP_ALIASES:
        return CROP_ALIASES[direct]
    return cleaned


async def forecast_crop_price(
    crop_type: str,
    region: str,
    forecast_days: int = 14
) -> dict:
    """
    Main price forecasting function.
    Uses real WFP data as primary source.
    """
    canonical_crop = _normalize_crop(crop_type)
    logger.info(
        f"Forecasting price: crop={canonical_crop}, "
        f"region={region}, days={forecast_days}"
    )

    # Try real data first
    real_forecast = get_real_price_forecast(
        canonical_crop, region, forecast_days
    )

    if real_forecast and real_forecast.get("is_real_data"):
        logger.info(
            f"Using real WFP price data for {canonical_crop} in {region}"
        )
        return real_forecast

    # Fallback to seasonal model
    logger.warning(
        f"No real price data for {canonical_crop} in {region} "
        f"— using seasonal estimate"
    )
    return _synthetic_forecast(canonical_crop, region, forecast_days)


def _synthetic_forecast(
    crop_type: str,
    region: str,
    forecast_days: int
) -> dict:
    """Fallback seasonal price forecast when real data unavailable."""
    today = datetime.now()

    # Get base price
    base = FALLBACK_BASE_PRICES.get(crop_type, {})
    region_lower = region.lower().strip()
    if region_lower in base:
        current_price = base[region_lower]
    elif base:
        current_price = sum(base.values()) / len(base)
    else:
        current_price = 500  # default

    # Apply inflation
    days_since_base = (today - BASE_DATE).days
    inflation = 1 + (ANNUAL_INFLATION * days_since_base / 365)
    current_price = round(current_price * inflation *
                         SEASONAL_PATTERN[today.month], 2)

    forecast = []
    for i in range(1, forecast_days + 1):
        target = today + timedelta(days=i)
        inf = 1 + (ANNUAL_INFLATION * (days_since_base + i) / 365)
        seasonal = SEASONAL_PATTERN[target.month]
        noise = 1 + 0.05 * np.sin((days_since_base + i) * 0.3)
        price = round(
            FALLBACK_BASE_PRICES.get(crop_type, {}).get(
                region.lower(), current_price
            ) * seasonal * inf * noise, 2
        )
        forecast.append({
            "date": target.strftime("%Y-%m-%d"),
            "day": i,
            "estimated_price_ngn": price,
            "day_label": target.strftime("%A, %b %d")
        })

    best = max(forecast, key=lambda x: x["estimated_price_ngn"])
    price_gain = round(
        (best["estimated_price_ngn"] - current_price) / current_price * 100, 1
    )

    if price_gain >= 5:
        recommendation = (
            f"Prices estimated to rise {price_gain}% by {best['day_label']}."
        )
    elif price_gain <= -5:
        recommendation = "Consider selling now — prices may fall."
    else:
        recommendation = "Prices stable. Sell based on your needs."

    first_half = np.mean(
        [f["estimated_price_ngn"] for f in forecast[:forecast_days//2]]
    )
    second_half = np.mean(
        [f["estimated_price_ngn"] for f in forecast[forecast_days//2:]]
    )
    trend = ("rising" if second_half > first_half * 1.03
             else "falling" if second_half < first_half * 0.97
             else "stable")

    return {
        "crop_type": crop_type,
        "region": region,
        "current_price_ngn": current_price,
        "forecast": forecast,
        "best_sell_day": best["day_label"],
        "best_sell_price_ngn": best["estimated_price_ngn"],
        "trend": trend,
        "recommendation": recommendation,
        "data_source": "Seasonal estimate (WFP data unavailable for this crop/region)",
        "is_real_data": False,
        "disclaimer": (
            "This is an estimate. Always verify with your local market."
        )
    }


# Keep _get_base_price and _estimate_price for backward compatibility
def _get_base_price(crop_type: str, region: str) -> Optional[float]:
    crop = _normalize_crop(crop_type)
    reg = region.lower().strip()
    if crop in FALLBACK_BASE_PRICES and reg in FALLBACK_BASE_PRICES[crop]:
        return FALLBACK_BASE_PRICES[crop][reg]
    if crop in FALLBACK_BASE_PRICES:
        prices = list(FALLBACK_BASE_PRICES[crop].values())
        return sum(prices) / len(prices)
    return None


def _estimate_price(crop_type: str, region: str,
                    target_date: datetime) -> float:
    base = _get_base_price(crop_type, region)
    if base is None:
        base = 500
    days_since_base = (target_date - BASE_DATE).days
    inflation = 1 + (ANNUAL_INFLATION * days_since_base / 365)
    seasonal = SEASONAL_PATTERN[target_date.month]
    noise = 1 + 0.05 * np.sin(days_since_base * 0.3)
    return round(base * seasonal * inflation * noise, 2)