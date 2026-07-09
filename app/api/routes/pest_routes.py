from fastapi import APIRouter, HTTPException
from app.models.schemas import PestDetectionRequest, PestDetectionResponse
from app.services.llm_service import ask_llm_structured
from loguru import logger
from datetime import datetime
import json
import re

router = APIRouter()

PEST_SYSTEM_PROMPT = """
You are an expert agricultural pathologist for West African crops.
A farmer will describe symptoms on their crop.

You MUST respond with ONLY a valid JSON object in this exact format:
{
  "detected_issue": "name of the disease or pest",
  "confidence": 0.85,
  "treatment": "specific treatment steps",
  "urgency": "low" or "medium" or "high"
}

Rules:
- confidence is a float between 0.0 and 1.0
- urgency must be exactly "low", "medium", or "high"
- treatment must be practical and mention specific products available in Nigeria
- detected_issue should be the common name + scientific name if known
- Return ONLY the JSON object. No extra text, no markdown.
"""

@router.post("/detect", response_model=PestDetectionResponse, tags=["Pest Detection"])
async def detect_pest(request: PestDetectionRequest):
  """
  Detect pest or disease from crop symptoms using LLM.
  """
  logger.info(f"Pest detection request: crop={request.crop_type}, region={request.region}")

  try:
    user_message = f"""
    Crop:{request.crop_type}
    Region: {request.region}
    Symptoms described by farmer: {request.symptoms}
    Analyze and respond in the required JSON format.
    """

    raw_response = await ask_llm_structured(user_message, PEST_SYSTEM_PROMPT)

    # Parse JSON response from LLM
    # Strip markdown code blocks if LLM adds them
    cleaned = re.sub(r"```json|```", "", raw_response).strip()
    data = json.loads(cleaned)

    return PestDetectionResponse(
      success=True,
      message="Pest detection complete",
      timestamp = datetime.utcnow(),
      crop_type = request.crop_type,
      detected_issue=data.get("detected_issue", "Unknown"),
      confidence = float(data.get("confidence", 0.0)),
      treatment=data.get("treatment", "No treatment found"),
      urgency= data.get("urgency", "medium")
    )

  except json.JSONDecodeError as e:
      logger.error(f"LLM returned invalid JSON: {raw_response}")
      raise HTTPException(status_code=500, detail="LLM returned unparseable response")
  except Exception as e:
      logger.error(f"Pest detection failed: {e}")
      raise HTTPException(status_code=500, detail=str(e))