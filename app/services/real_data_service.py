"""
Real Data Service — replaces synthetic data with real Nigerian agricultural data.

Data sources:
- WFP/HDX: Real Nigerian food prices (2002-2026)
- Our World in Data (FAO): Real crop yields for Nigeria
- NASA POWER: Real historical weather by Nigerian state
"""
import pandas as pd
import json
import numpy as np
from pathlib import Path
from datetime import datetime, date
from typing import Optional
from loguru import logger

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "real"

# ── Load data at module startup (cached in memory) ──
_price_df: Optional[pd.DataFrame] = None
_yield_data: Optional[dict] = None
_weather_data: Optional[dict] = None


def _load_price_data() -> Optional[pd.DataFrame]:
    """Loads WFP price data into memory."""
    global _price_df
    if _price_df is not None:
        return _price_df

    price_file = DATA_DIR / "wfp_prices_nigeria.csv"
    if not price_file.exists():
        logger.warning("WFP price data not found — falling back to synthetic")
        return None

    try:
        df = pd.read_csv(price_file)
        df["date"] = pd.to_datetime(df["date"])
        df["state_lower"] = df["state"].str.lower().str.strip()
        df["crop_lower"] = df["crop_type"].str.lower().str.strip()
        _price_df = df
        logger.info(f"Loaded {len(df)} real price records from WFP data")
        return df
    except Exception as e:
        logger.error(f"Failed to load price data: {e}")
        return None


def _load_yield_data() -> Optional[dict]:
    """Loads OWID/FAO yield data into memory."""
    global _yield_data
    if _yield_data is not None:
        return _yield_data

    yield_file = DATA_DIR / "real_yields_nigeria.json"
    if not yield_file.exists():
        logger.warning("Yield data not found — falling back to synthetic")
        return None

    try:
        with open(yield_file) as f:
            _yield_data = json.load(f)
        logger.info(f"Loaded real yield data for {len(_yield_data)} crops")
        return _yield_data
    except Exception as e:
        logger.error(f"Failed to load yield data: {e}")
        return None


def _load_weather_data() -> Optional[dict]:
    """Loads NASA POWER weather data into memory."""
    global _weather_data
    if _weather_data is not None:
        return _weather_data

    weather_file = DATA_DIR / "nasa_weather_nigeria.json"
    if not weather_file.exists():
        logger.warning("NASA weather data not found — falling back to OpenWeather")
        return None

    try:
        with open(weather_file) as f:
            _weather_data = json.load(f)
        logger.info(f"Loaded NASA weather data for {len(_weather_data)} regions")
        return _weather_data
    except Exception as e:
        logger.error(f"Failed to load weather data: {e}")
        return None


# ── Initialize on import ──
_load_price_data()
_load_yield_data()
_load_weather_data()


# ────────────────────────────────────────────
# PRICE FUNCTIONS
# ────────────────────────────────────────────

def get_real_current_price(crop_type: str, region: str) -> Optional[dict]:
    """
    Gets the most recent real WFP price for a crop in a region.
    Falls back to national average if region not found.
    """
    df = _load_price_data()
    if df is None:
        return None

    crop = crop_type.lower().strip()
    state = region.lower().strip()

    # Filter by crop
    crop_df = df[df["crop_lower"] == crop]
    if len(crop_df) == 0:
        # Try partial match
        crop_df = df[df["crop_lower"].str.contains(crop, na=False)]

    if len(crop_df) == 0:
        logger.warning(f"No price data for crop: {crop}")
        return None

    # Try state-specific price first
    state_df = crop_df[crop_df["state_lower"].str.contains(state, na=False)]

    if len(state_df) > 0:
        latest = state_df.sort_values("date").tail(20)
        source = f"{region} markets"
    else:
        # Fall back to national average
        latest = crop_df.sort_values("date").tail(50)
        source = "national average (state data unavailable)"
        logger.info(f"No price data for {crop} in {region} — using national average")

    # Use retail prices preferentially
    retail = latest[latest["price_type"] == "Retail"]
    if len(retail) > 0:
        latest = retail

    avg_price = latest["price_ngn"].mean()
    min_price = latest["price_ngn"].min()
    max_price = latest["price_ngn"].max()
    most_recent_date = latest["date"].max()

    # Calculate price trend (compare last 6 months vs previous 6 months)
    six_months_ago = pd.Timestamp.now() - pd.DateOffset(months=6)
    twelve_months_ago = pd.Timestamp.now() - pd.DateOffset(months=12)

    recent = crop_df[crop_df["date"] >= six_months_ago]["price_ngn"]
    older = crop_df[
        (crop_df["date"] >= twelve_months_ago) &
        (crop_df["date"] < six_months_ago)
    ]["price_ngn"]

    if len(recent) > 0 and len(older) > 0:
        recent_avg = recent.mean()
        older_avg = older.mean()
        change_pct = ((recent_avg - older_avg) / older_avg) * 100

        if change_pct > 10:
            trend = "rising"
        elif change_pct < -10:
            trend = "falling"
        else:
            trend = "stable"
        trend_pct = round(change_pct, 1)
    else:
        trend = "stable"
        trend_pct = 0.0

    return {
        "crop_type": crop,
        "region": region,
        "current_price_ngn": round(avg_price, 2),
        "price_range_ngn": {
            "min": round(min_price, 2),
            "max": round(max_price, 2)
        },
        "trend": trend,
        "trend_change_pct": trend_pct,
        "data_source": f"WFP Market Monitoring — {source}",
        "last_updated": str(most_recent_date)[:10],
        "is_real_data": True
    }


def get_real_price_forecast(
    crop_type: str,
    region: str,
    forecast_days: int = 14
) -> dict:
    """
    Generates price forecast using real WFP historical data.
    Uses seasonal patterns extracted from real data.
    """
    from datetime import timedelta

    df = _load_price_data()
    crop = crop_type.lower().strip()

    # Get real current price
    real_price = get_real_current_price(crop, region)

    if real_price:
        current_price = real_price["current_price_ngn"]
        trend = real_price["trend"]
        trend_pct = real_price["trend_change_pct"]
        data_source = real_price["data_source"]
        is_real = True
    else:
        # Fallback to synthetic
        from app.services.price_service import _estimate_price
        current_price = _estimate_price(crop, region, datetime.now())
        trend = "stable"
        trend_pct = 0.0
        data_source = "Estimated (no real data available for this crop/region)"
        is_real = False

    # Generate seasonal forecast using real monthly patterns
    forecast = []
    today = datetime.now()

    # Extract real seasonal multipliers from WFP data
    seasonal_multipliers = _get_real_seasonal_multipliers(crop, df)

    for i in range(1, forecast_days + 1):
        target_date = today + timedelta(days=i)
        month = target_date.month

        # Apply real seasonal pattern
        seasonal_factor = seasonal_multipliers.get(month, 1.0)

        # Apply trend
        daily_trend = (trend_pct / 100) / 180  # spread over 6 months
        trend_factor = 1 + (daily_trend * i)

        # Small deterministic variation
        variation = 1 + 0.02 * np.sin(i * 0.5)

        forecasted_price = round(
            current_price * seasonal_factor * trend_factor * variation, 2
        )

        forecast.append({
            "date": target_date.strftime("%Y-%m-%d"),
            "day": i,
            "estimated_price_ngn": forecasted_price,
            "day_label": target_date.strftime("%A, %b %d")
        })

    # Best sell day
    best = max(forecast, key=lambda x: x["estimated_price_ngn"])
    price_gain_pct = round(
        (best["estimated_price_ngn"] - current_price) / current_price * 100, 1
    )

    if price_gain_pct >= 5:
        recommendation = (
            f"Based on real WFP market data, prices are expected to rise "
            f"{price_gain_pct}% by {best['day_label']}. "
            f"Consider waiting to sell. Best estimated price: "
            f"₦{best['estimated_price_ngn']:,.0f}/kg."
        )
    elif price_gain_pct <= -5:
        recommendation = (
            f"Based on real market data, prices are expected to fall. "
            f"Current price of ₦{current_price:,.0f}/kg is near the peak. "
            f"Consider selling soon."
        )
    else:
        recommendation = (
            f"Prices are relatively stable around ₦{current_price:,.0f}/kg "
            f"based on real WFP market monitoring. "
            f"Sell based on your storage capacity and cash flow needs."
        )

    # Determine overall trend for forecast window
    first_half_avg = np.mean(
        [f["estimated_price_ngn"] for f in forecast[:forecast_days//2]]
    )
    second_half_avg = np.mean(
        [f["estimated_price_ngn"] for f in forecast[forecast_days//2:]]
    )

    if second_half_avg > first_half_avg * 1.03:
        forecast_trend = "rising"
    elif second_half_avg < first_half_avg * 0.97:
        forecast_trend = "falling"
    else:
        forecast_trend = "stable"

    return {
        "crop_type": crop,
        "region": region,
        "current_price_ngn": current_price,
        "forecast": forecast,
        "best_sell_day": best["day_label"],
        "best_sell_price_ngn": best["estimated_price_ngn"],
        "trend": forecast_trend,
        "recommendation": recommendation,
        "data_source": data_source,
        "is_real_data": is_real,
        "disclaimer": (
            "Prices based on WFP market monitoring data. "
            "Always verify with your local market before selling."
        )
    }


def _get_real_seasonal_multipliers(
    crop: str,
    df: Optional[pd.DataFrame]
) -> dict:
    """
    Extracts real seasonal price patterns from WFP data.
    Returns monthly multipliers based on actual historical averages.
    """
    if df is None:
        # Default seasonal pattern
        return {
            1: 1.15, 2: 1.20, 3: 1.10, 4: 0.95,
            5: 0.90, 6: 0.88, 7: 0.92, 8: 0.95,
            9: 1.00, 10: 0.85, 11: 0.88, 12: 1.10
        }

    crop_df = df[df["crop_lower"] == crop]
    if len(crop_df) == 0:
        return {i: 1.0 for i in range(1, 13)}

    # Calculate average price by month from real data
    crop_df = crop_df.copy()
    crop_df["month"] = crop_df["date"].dt.month
    monthly_avgs = crop_df.groupby("month")["price_ngn"].mean()

    if len(monthly_avgs) == 0:
        return {i: 1.0 for i in range(1, 13)}

    overall_avg = monthly_avgs.mean()
    multipliers = {}

    for month in range(1, 13):
        if month in monthly_avgs.index:
            multipliers[month] = round(monthly_avgs[month] / overall_avg, 3)
        else:
            multipliers[month] = 1.0

    return multipliers


# ────────────────────────────────────────────
# YIELD FUNCTIONS
# ────────────────────────────────────────────

def get_real_yield_baseline(crop_type: str) -> Optional[float]:
    """
    Gets real FAO yield baseline for a Nigerian crop (kg/ha).
    Uses most recent available year.
    """
    yield_data = _load_yield_data()
    if yield_data is None:
        return None

    crop = crop_type.lower().strip()

    # Direct match
    if crop in yield_data:
        years = yield_data[crop]
        if years:
            # Use most recent year
            latest_year = max(int(y) for y in years.keys())
            return years[str(latest_year)]

    return None


def get_real_weather_for_region(region: str, month: Optional[int] = None) -> Optional[dict]:
    """
    Gets real NASA POWER weather data for a Nigerian region.
    If month is specified, returns that month's averages.
    Otherwise returns annual averages.
    """
    weather_data = _load_weather_data()
    if weather_data is None:
        return None

    # Find matching region
    region_key = None
    for key in weather_data.keys():
        if key.lower() == region.lower() or region.lower() in key.lower():
            region_key = key
            break

    if not region_key:
        logger.warning(f"No NASA weather data for region: {region}")
        return None

    region_data = weather_data[region_key]
    monthly = region_data.get("monthly_averages", {})

    if month:
        month_data = monthly.get(str(month)) or monthly.get(month)
        if month_data:
            return {
                "region": region,
                "month": month,
                "temperature_celsius": month_data["avg_temp_celsius"],
                "rainfall_mm": month_data["avg_rainfall_mm"],
                "humidity_pct": month_data["avg_humidity_pct"],
                "data_source": "NASA POWER (10-year historical average)",
                "is_real_data": True
            }
    else:
        # Annual averages
        if monthly:
            temps = [v["avg_temp_celsius"] for v in monthly.values()]
            rains = [v["avg_rainfall_mm"] for v in monthly.values()]
            humidity = [v["avg_humidity_pct"] for v in monthly.values()]

            return {
                "region": region,
                "avg_annual_temp_celsius": round(
                    sum(temps) / len(temps), 1
                ),
                "avg_annual_rainfall_mm": round(sum(rains), 1),
                "avg_humidity_pct": round(
                    sum(humidity) / len(humidity), 1