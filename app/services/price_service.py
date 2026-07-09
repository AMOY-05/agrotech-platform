import numpy as np
from datetime import datetime, timedelta
from loguru import logger
from typing import Optional

# Base prices in Naira per kg — our ground truth anchor
BASE_PRICES = {
    "tomato":   {"lagos": 800,  "kano": 600,  "oyo": 700,  "rivers": 900,  "kaduna": 650},
    "maize":    {"lagos": 450,  "kano": 380,  "oyo": 420,  "rivers": 480,  "kaduna": 400},
    "cassava":  {"lagos": 200,  "kano": 180,  "oyo": 190,  "rivers": 220,  "kaduna": 185},
    "rice":     {"lagos": 950,  "kano": 880,  "oyo": 920,  "rivers": 980,  "kaduna": 900},
    "yam":      {"lagos": 600,  "kano": 500,  "oyo": 550,  "rivers": 650,  "kaduna": 520},
    "pepper":   {"lagos": 1200, "kano": 1000, "oyo": 1100, "rivers": 1300, "kaduna": 1050},
    "cowpea":   {"lagos": 700,  "kano": 580,  "oyo": 650,  "rivers": 750,  "kaduna": 600},
    "plantain": {"lagos": 400,  "kano": 350,  "oyo": 380,  "rivers": 450,  "kaduna": 360},
}

SEASONAL_PATTERN = {
    1: 1.15, 2: 1.20, 3: 1.10, 4: 0.95, 5: 0.90,
    6: 0.88, 7: 0.92, 8: 0.95, 9: 1.00, 10: 0.85,
    11: 0.88, 12: 1.10
}

# Annual inflation factor (Nigerian food inflation ~15%)
ANNUAL_INFLATION = 0.15

# Reference date our base prices are anchored to
BASE_DATE = datetime(2024, 1, 1)


# Mapping of common variations to canonical crop names
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
    """Normalizes crop name to match our price table keys."""
    cleaned = crop_type.lower().strip().rstrip("s")  # remove trailing 's' as a base rule
    # Check alias table first for irregular cases
    direct = crop_type.lower().strip()
    if direct in CROP_ALIASES:
        return CROP_ALIASES[direct]
    return cleaned


def _get_base_price(crop_type: str, region: str) -> Optional[float]:
    """Looks up base price, handles fuzzy region/crop matching."""
    crop = _normalize_crop(crop_type)
    reg = region.lower().strip()

    # Try direct match first
    if crop in BASE_PRICES and reg in BASE_PRICES[crop]:
        return BASE_PRICES[crop][reg]

    # Crop exists but region not found — use average across regions
    if crop in BASE_PRICES:
        prices = list(BASE_PRICES[crop].values())
        logger.warning(f"Region '{region}' not in price table — using crop average")
        return sum(prices) / len(prices)

    # Last resort — log clearly so we know what farmers are asking for
    logger.warning(f"Unknown crop '{crop_type}' (normalized: '{crop}') — not in price table")
    return None


def _estimate_price(crop_type: str, region: str, target_date: datetime) -> float:
    """
    Estimates price for a given crop/region/date using:
    - Base price anchor
    - Seasonal multiplier
    - Inflation adjustment
    - Small random market noise
    """
    base = _get_base_price(crop_type, region)
    if base is None:
        raise ValueError(f"Unknown crop type: '{crop_type}'")

    days_since_base = (target_date - BASE_DATE).days
    inflation = 1 + (ANNUAL_INFLATION * days_since_base / 365)
    seasonal = SEASONAL_PATTERN[target_date.month]

    # Deterministic noise based on date (reproducible, not random each call)
    noise = 1 + 0.05 * np.sin(days_since_base * 0.3)

    return round(base * seasonal * inflation * noise, 2)


async def forecast_crop_price(
    crop_type: str,
    region: str,
    forecast_days: int = 14
) -> dict:
    """
    Forecasts crop price for the next N days.
    Returns current price, daily forecast, best sell day, and trend.
    """
    canonical_crop = _normalize_crop(crop_type)
    logger.info(f"Forecasting price: crop={canonical_crop}, region={region}, days={forecast_days}")

    today = datetime.now()
    current_price = _estimate_price(canonical_crop, region, today)

    # Generate daily forecast
    forecast = []
    for i in range(1, forecast_days + 1):
        target_date = today + timedelta(days=i)
        price = _estimate_price(canonical_crop, region, target_date)
        forecast.append({
            "date": target_date.strftime("%Y-%m-%d"),
            "day": i,
            "estimated_price_ngn": price,
            "day_label": target_date.strftime("%A, %b %d")
        })

    # Find best sell day (highest price in forecast window)
    best = max(forecast, key=lambda x: x["estimated_price_ngn"])

    # Determine trend
    avg_first_half = np.mean([f["estimated_price_ngn"] for f in forecast[:forecast_days//2]])
    avg_second_half = np.mean([f["estimated_price_ngn"] for f in forecast[forecast_days//2:]])

    if avg_second_half > avg_first_half * 1.03:
        trend = "rising"
    elif avg_second_half < avg_first_half * 0.97:
        trend = "falling"
    else:
        trend = "stable"

    # Generate sell recommendation
    price_gain_pct = round((best["estimated_price_ngn"] - current_price) / current_price * 100, 1)

    if price_gain_pct >= 5:
        recommendation = (
            f"Wait to sell — prices are expected to rise {price_gain_pct}% "
            f"by {best['day_label']}. Estimated price: ₦{best['estimated_price_ngn']:,.0f}/kg."
        )
    elif price_gain_pct <= -5:
        recommendation = (
            f"Sell now — prices are expected to fall. "
            f"Current price of ₦{current_price:,.0f}/kg is near the peak."
        )
    else:
        recommendation = (
            f"Prices are relatively stable around ₦{current_price:,.0f}/kg. "
            f"Sell based on your storage capacity and cash flow needs."
        )

    logger.info(f"Price forecast complete: current=₦{current_price}, trend={trend}, best day={best['day_label']}")

    return {
        "crop_type": canonical_crop,
        "region": region,
        "current_price_ngn": current_price,
        "forecast": forecast,
        "best_sell_day": best["day_label"],
        "best_sell_price_ngn": best["estimated_price_ngn"],
        "trend": trend,
        "recommendation": recommendation
    }