from loguru import logger

# --- Tool Definitions (Sent to LLM so it knows what's available) ---

AGENT_TOOLS = [
  {
    "type": "function",
    "function":{
      "name": "detect_pest_disease",
      "description": "Identify a crop pest or disease based on described symptoms. Use this whenever a farmer mentions symptoms like spots, wilting, discoloration, holes in leaves, or pest sightings.",
      "parameters": {
        "type": "object",
        "properties": {
          "crop_type": {
            "type": "string",
            "description": "The crop affected, e.g. tomato, maize, cassava"
          },
          "symptoms":{
            "type": "string",
            "description": "Description of what the farmer is seeing on the crop"
          }
        },
        "required": ["crop_type", "symptoms"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "forecast_price",
      "description": "Get market price forecast for a crop to help farmer decide when to sell. Use this whenever a farmer asks about selling, pricing, market timing, or 'when should I sell'.",
      "parameters": {
        "type": "object",
        "properties": {
          "crop_type": {
            "type": "string",
            "description": "The crop to forecast price for"
          },
          "region":{
            "type": "string",
            "description": "Nigerian state or region, e.g. Lagos, Kano, Oyo"
          }
        },
        "required": ["crop_type", "region"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "predict_yield",
      "description": "Predict expected crop yield based on farm conditions. Use this when a farmer asks how much they will harvest or wants yield estimates.",
      "parameters": {
        "type": "object",
        "properties": {
          "crop_type": {"type": "string"},
          "farm_size_hectares": {"type": "number"},
          "region": {"type": "string"}
        },
        "required": ["crop_type", "farm_size_hectares", "region"]
      }
    }
  },
  {
    "type": "function",
    "function": {
        "name": "find_nearby_stores",
        "description": "Find nearby agro-input stores, markets, or suppliers for a farmer. Use this when a farmer asks where to buy insecticides, fertilizers, seeds, farm equipment, animal feed, or any farm inputs near their location.",
        "parameters": {
            "type": "object",
            "properties": {
                "region": {
                    "type": "string",
                    "description": "Nigerian state or city where the farmer is located, e.g. Bauchi, Lagos, Kano"
                },
                "query": {
                    "type": "string",
                    "description": "What the farmer is looking for, e.g. insecticide store, fertilizer, seeds, farm equipment"
                }
            },
            "required": ["region", "query"]
        }
    }
  }
]

# --- Tool Execution Functions (the actual logic each tool runs) ---
async def execute_detect_pest_disease(crop_type: str, symptoms: str) -> dict:
  """Wraps the past detection logic for agent use."""
  from app.services.llm_service import ask_llm_structured
  import json
  import re

  logger.info(f"[TOOL] detect_pest_disease called: crop={crop_type}")

  prompt = f"""
  You are an expert agricultural pathologist for West African crops.
  Crop: {crop_type}
  Symptoms: {symptoms}

  Respond with ONLY this JSON format:
  {{"detected_issue": "...", "confidence": 0.0, "treatment": "...", "urgency": "low/medium/high"}}
  """
  raw = await ask_llm_structured(prompt, prompt, temperature=0.3)
  cleaned = re.sub(r"```json|```", "", raw).strip()
  return json.loads(cleaned)

async def execute_forecast_price(crop_type: str, region: str) -> dict:
    """Real price forecast using seasonal model."""
    from app.services.price_service import forecast_crop_price

    logger.info(f"[TOOL] forecast_price called: crop={crop_type}, region={region}")

    result = await forecast_crop_price(crop_type=crop_type, region=region, forecast_days=14)

    return {
        "crop_type": crop_type,
        "region": region,
        "current_price_ngn": result["current_price_ngn"],
        "best_sell_day": result["best_sell_day"],
        "best_sell_price_ngn": result["best_sell_price_ngn"],
        "trend": result["trend"],
        "recommendation": result["recommendation"]
    }

async def execute_predict_yield(crop_type: str, farm_size_hectares: float, region: str) -> dict:
    """Real ML-based yield prediction using trained XGBoost model + live weather forecast data."""
    import asyncio
    from app.services.yield_service import predict_yield_ml
    from app.services.weather_service import get_current_weather, get_estimated_monthly_rainfall

    logger.info(f"[TOOL] predict_yield called: crop={crop_type}, size={farm_size_hectares}")

    try:
        # Run both weather calls concurrently instead of one after another
        current_weather, rainfall = await asyncio.gather(
            get_current_weather(region),
            get_estimated_monthly_rainfall(region)
        )
        temperature = current_weather["temperature_celsius"]
        rainfall = max(rainfall, 200)
        weather_source = "live"
        logger.info(f"[TOOL] Using live weather: {temperature}°C, ~{rainfall}mm/month estimate")
    except Exception as e:
        logger.warning(f"[TOOL] Weather fetch failed, using defaults: {e}")
        rainfall = 1200
        temperature = 27
        weather_source= "default_fallback"

    result = await predict_yield_ml(
        crop_type=crop_type,
        farm_size_hectares=farm_size_hectares,
        region=region,
        soil_type="loamy",
        rainfall_mm=rainfall,
        temperature_celsius=temperature,
        fertilizer_used=True
    )

    return {
        "crop_type": crop_type,
        "farm_size_hectares": farm_size_hectares,
        "predicted_yield_kg": result["predicted_yield_kg"],
        "weather_used": {
            "temperature_celsius": temperature,
            "estimated_monthly_rainfall_mm": rainfall,
            "data_source": weather_source
        },
        "note": "Estimate uses live weather forecast data — provide soil type and fertilizer use for a more precise prediction" if weather_source=="live" else "Weather service was temporarily unavailable - this estimate uses typical regional averages rather than today's actual conditions"
    }
async def execute_find_nearby_stores(region: str, query: str) -> dict:
    """Finds nearby agro-input stores using Google Places API."""
    from app.services.location_service import find_nearby_agro_stores

    logger.info(f"[TOOL] find_nearby_stores called: region={region}, query={query}")

    result = await find_nearby_agro_stores(region=region, query=query)
    return result
# --- Tool Router

TOOL_FUNCTIONS = {
  "detect_pest_disease": execute_detect_pest_disease,
  "forecast_price": execute_forecast_price,
  "predict_yield": execute_predict_yield,
  "find_nearby_stores": execute_find_nearby_stores
}


async def run_tool(tool_name:str, arguments:dict) -> dict:
  """Executes the correct tool function based on name."""
  if tool_name not in TOOL_FUNCTIONS:
    raise ValueError(f"Unknown tool: {tool_name}")


  func = TOOL_FUNCTIONS[tool_name]
  return await func(**arguments) 