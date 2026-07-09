import httpx
from app.core.config import settings
from loguru import logger
from typing import Optional

OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5"

# Nigerian state capitals — used to resolve region names to coordinates
# (OpenWeather works better with city names than vague "region" strings)
NIGERIAN_REGIONS = {
    "lagos": "Lagos,NG",
    "kano": "Kano,NG",
    "abuja": "Abuja,NG",
    "oyo": "Ibadan,NG",
    "rivers": "Port Harcourt,NG",
    "kaduna": "Kaduna,NG",
    "enugu": "Enugu,NG",
    "bauchi": "Bauchi,NG",
    "plateau": "Jos,NG",
    "benue": "Makurdi,NG",
    "ogun": "Abeokuta,NG",
    "delta": "Asaba,NG",
    "anambra": "Awka,NG",
    "katsina": "Katsina,NG",
    "sokoto": "Sokoto,NG",
}

# Reusable client for connection pooling — avoids re-establishing TLS handshake every call
_http_client: Optional[httpx.AsyncClient] = None

async def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=10.0)
    return _http_client

def resolve_region_to_city(region: str) -> str:
    """Maps a farmer's region input to a city name OpenWeather understands."""
    key = region.strip().lower()
    return NIGERIAN_REGIONS.get(key, f"{region},NG")


async def get_current_weather(region: str) -> dict:
    """
    Fetches current weather conditions for a Nigerian region.
    Returns temperature, humidity, rainfall, and conditions.
    """
    city = resolve_region_to_city(region)
    logger.info(f"Fetching weather for: {city}")

    try:
        client = await get_http_client()    
        response = await client.get(
            f"{OPENWEATHER_BASE_URL}/weather",
            params={
                "q": city,
                "appid": settings.openweather_api_key,
                "units": "metric"  # Celsius, not Fahrenheit
            }
        )
        response.raise_for_status()
        data = response.json()

        result = {
            "region": region,
            "city_resolved": city,
            "temperature_celsius": data["main"]["temp"],
            "humidity_percent": data["main"]["humidity"],
            "conditions": data["weather"][0]["description"],
            "rainfall_mm_last_hour": data.get("rain", {}).get("1h", 0),
            "wind_speed_ms": data["wind"]["speed"]
        }

        logger.info(f"Weather fetched: {result['temperature_celsius']}°C, {result['humidity_percent']}% humidity")
        return result

    except httpx.HTTPStatusError as e:
        logger.error(f"OpenWeather API error: {e.response.status_code} — {e.response.text}")
        raise Exception(f"Could not fetch weather for {region}: API returned {e.response.status_code}")
    except httpx.RequestError as e:
        logger.error(f"OpenWeather request failed: {e}")
        raise Exception(f"Weather service unavailable: {str(e)}")
    except KeyError as e:
        logger.error(f"Unexpected weather API response format: {e}")
        raise Exception("Weather data format error")


async def get_5day_forecast(region: str) -> dict:
    """
    Fetches 5-day weather forecast — useful for yield prediction
    (predicted rainfall) and sell-timing advice (weather affecting transport/storage).
    """
    city = resolve_region_to_city(region)
    logger.info(f"Fetching 5-day forecast for: {city}")

    try:
        client = await get_http_client()
        response = await client.get(
            f"{OPENWEATHER_BASE_URL}/forecast",
            params={
                "q": city,
                "appid": settings.openweather_api_key,
                "units": "metric"
            }
        )
        response.raise_for_status()
        data = response.json()

        # OpenWeather gives 3-hour intervals — we summarize into daily averages
        daily_summary = {}
        for entry in data["list"]:
            date = entry["dt_txt"].split(" ")[0]
            if date not in daily_summary:
                daily_summary[date] = {
                    "temps": [],
                    "rainfall": 0,
                    "conditions": []
                }
            daily_summary[date]["temps"].append(entry["main"]["temp"])
            daily_summary[date]["rainfall"] += entry.get("rain", {}).get("3h", 0)
            daily_summary[date]["conditions"].append(entry["weather"][0]["main"])

        forecast = []
        for date, info in list(daily_summary.items())[:5]:
            forecast.append({
                "date": date,
                "avg_temp_celsius": round(sum(info["temps"]) / len(info["temps"]), 1),
                "total_rainfall_mm": round(info["rainfall"], 1),
                "dominant_condition": max(set(info["conditions"]), key=info["conditions"].count)
            })

        logger.info(f"5-day forecast fetched: {len(forecast)} days for {city}")
        return {
            "region": region,
            "city_resolved": city,
            "forecast": forecast
        }

    except httpx.HTTPStatusError as e:
        logger.error(f"OpenWeather forecast error: {e.response.status_code}")
        raise Exception(f"Could not fetch forecast for {region}: API returned {e.response.status_code}")
    except httpx.RequestError as e:
        logger.error(f"OpenWeather forecast request failed: {e}")
        raise Exception(f"Forecast service unavailable: {str(e)}")

async def get_estimated_monthly_rainfall(region: str) -> float:
    """
    Estimates monthly rainfall by summing the 5-day forecast total
    and extrapolating to 30 days. More grounded than a single-hour reading,
    though still an approximation since forecasts get less reliable past ~5 days.
    """
    forecast_data = await get_5day_forecast(region)
    total_5day_rainfall = sum(day["total_rainfall_mm"] for day in forecast_data["forecast"])

    # Extrapolate 5-day total to a 30-day estimate
    daily_avg = total_5day_rainfall / len(forecast_data["forecast"]) if forecast_data["forecast"] else 0
    monthly_estimate = round(daily_avg * 30, 1)

    logger.info(f"Estimated monthly rainfall for {region}: {monthly_estimate}mm (from {total_5day_rainfall}mm over 5 days)")
    return monthly_estimate