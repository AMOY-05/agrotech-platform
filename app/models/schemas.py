# Creating the Response Model

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

# --- Base Response Wrapper ---
class BaseResponse(BaseModel):
  success: bool
  message: str
  timestamp: datetime = datetime.utcnow()


# --- Health Check ---
class HealthResponse(BaseModel):
  status: str
  version: str
  platform: str

# --- Pest Detection ---
class PestDetectionRequest(BaseModel):
  crop_type: str
  symptoms: str
  region: str

class PestDetectionResponse(BaseResponse):
  crop_type: str
  detected_issue: str
  confidence: float
  treatment: str
  urgency: str # 'Low', 'Medium', 'High'

# ---Yield Prediction ---
class YieldPredictionRequest(BaseModel):
  crop_type: str
  farm_size_hectares: float
  region: str
  soil_type: str
  rainfall_mm: float
  temperature_celsius: float
  fertilizer_used: bool

class YieldPredictionResponse(BaseResponse):
  crop_type: str
  predicted_yield_kg: float
  confidence_interval: dict
  recommendation: str

  
# ---Price Forecast---
class PriceForecastRequest(BaseModel):
  crop_type: str
  region: str
  forecast_days: int = 14

class PriceForecastResponse(BaseResponse):
  crop_type: str
  region: str
  current_price_ngn: float
  forecast: List[dict]
  best_sell_day: str
  trend: str # "rising", "falling", "stable"

# ---Agent Chat ---
class ChatRequest(BaseModel):
    message: str
    farmer_id: Optional[str] = None
    crop_context: Optional[str] = None
    preferred_language: Optional[str] = "english"

class ChatResponse(BaseResponse):
    reply: str
    sources: Optional[List[str]] = []
    session_context: Optional[dict] = {}

