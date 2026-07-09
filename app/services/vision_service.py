import base64
import json
import re
from groq import Groq
from app.core.config import settings
from loguru import logger
from typing import Optional

client = Groq(api_key=settings.groq_api_key)

# Stage 1: Identify the crop first
CROP_IDENTIFICATION_PROMPT = """
You are an expert botanist specializing in West African crops.

Look at this plant image carefully. Your ONLY job right now is to identify 
what crop/plant this is.

Respond with ONLY this JSON:
{
  "crop_identified": "specific crop name or 'unknown'",
  "crop_confidence": 0.85,
  "crop_family": "plant family if known",
  "visible_parts": ["leaf", "stem", "fruit", "root", "flower"],
  "identification_notes": "brief notes on what visual features helped identify it"
}

CRITICAL RULES:
- If you cannot confidently identify the crop, set crop_identified to "unknown"
- NEVER guess a crop just because the disease pattern looks familiar
- Common West African crops: tomato, maize, cassava, yam, rice, pepper, 
  cowpea, plantain, groundnut, soybean, sorghum, millet, okra, spinach,
  watermelon, cucumber, cocoa, palm oil, sugarcane, banana
- Return ONLY the JSON. No extra text.
"""

# Stage 2: Diagnose disease given crop context
DISEASE_DIAGNOSIS_PROMPT = """
You are an expert agricultural pathologist for West African crops, 
particularly Nigeria, Ghana, and surrounding countries.

A farmer has sent a photo of their {crop_context} crop showing signs of 
possible disease or pest damage.

Analyze the visible symptoms carefully and respond with ONLY this JSON:
{{
  "detected_issue": "specific disease/pest name (common name + scientific name)",
  "confidence": 0.85,
  "severity": "mild/moderate/severe",
  "urgency": "low/medium/high",
  "symptoms_visible": ["list", "of", "visible", "symptoms"],
  "treatment": "specific step-by-step treatment with products available in Nigeria",
  "prevention": "specific prevention measures for future seasons",
  "estimated_yield_impact": "e.g. 20-40% yield loss if untreated"
}}

CRITICAL RULES:
- Base your diagnosis ONLY on what you can actually see in the image
- If multiple diseases are possible, list the most likely one with honest confidence
- If the image is unclear, set confidence below 0.4 and note it in symptoms_visible
- NEVER fabricate a diagnosis you cannot support from the visual evidence
- urgency must be exactly "low", "medium", or "high"
- severity must be exactly "mild", "moderate", or "severe"
- confidence is a float between 0.0 and 1.0
- Return ONLY the JSON. No extra text.
"""

# Fallback: when crop cannot be identified
UNKNOWN_CROP_DIAGNOSIS_PROMPT = """
You are an expert agricultural pathologist for West African crops.

A farmer has sent a photo of a plant you could not confidently identify.
Focus ONLY on the visible symptoms, damage patterns, and signs of disease 
or pest attack — regardless of what crop it is.

Respond with ONLY this JSON:
{
  "detected_issue": "general disease/pest category based on visible symptoms",
  "confidence": 0.5,
  "severity": "mild/moderate/severe", 
  "urgency": "low/medium/high",
  "symptoms_visible": ["list", "of", "what", "you", "can", "see"],
  "possible_causes": ["list", "of", "possible", "diseases", "or", "pests"],
  "treatment": "general treatment advice applicable to most crops",
  "prevention": "general prevention advice",
  "estimated_yield_impact": "varies depending on crop and disease progression",
  "recommendation": "Take this photo to your nearest agricultural extension officer for precise identification"
}

RULES:
- Be honest — describe what you SEE, not what you assume
- List multiple possible causes since crop is unknown
- confidence should reflect your actual certainty (likely 0.3-0.6 for unknown crops)
- Return ONLY the JSON. No extra text.
"""


async def _call_vision_model(
    image_base64: str,
    image_media_type: str,
    system_prompt: str,
    user_text: str,
    temperature: float = 0.2
) -> str:
    """Core function to call Groq vision model."""
    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{image_media_type};base64,{image_base64}"
                        }
                    },
                    {"type": "text", "text": user_text}
                ]
            }
        ],
        temperature=temperature,
        max_tokens=800
    )
    return response.choices[0].message.content


def _parse_json_response(raw: str) -> dict:
    """Safely parses JSON from model response."""
    cleaned = re.sub(r"```json|```", "", raw).strip()
    return json.loads(cleaned)


async def analyze_crop_image(
    image_bytes: bytes,
    image_media_type: str = "image/jpeg",
    additional_context: Optional[str] = None,
    known_crop_type: Optional[str] = None
) -> dict:
    """
    Two-stage crop image analysis:
    Stage 1 — Identify the crop
    Stage 2 — Diagnose disease based on confirmed crop identity
    """
    logger.info(f"Analyzing crop image: {len(image_bytes)} bytes, "
                f"known_crop={known_crop_type}")

    try:
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        # ── STAGE 1: Crop Identification ──
        if known_crop_type:
            # Farmer told us what crop it is — trust them, skip identification
            crop_identified = known_crop_type.lower().strip()
            crop_confidence = 1.0
            visible_parts = []
            logger.info(f"Crop provided by farmer: {crop_identified}")
        else:
            logger.info("Stage 1: Identifying crop from image...")
            raw_id = await _call_vision_model(
                image_base64=image_base64,
                image_media_type=image_media_type,
                system_prompt=CROP_IDENTIFICATION_PROMPT,
                user_text="What crop or plant is in this image? Be precise and honest about uncertainty.",
                temperature=0.1
            )

            try:
                id_result = _parse_json_response(raw_id)
                crop_identified = id_result.get("crop_identified", "unknown").lower()
                crop_confidence = float(id_result.get("crop_confidence", 0.5))
                visible_parts = id_result.get("visible_parts", [])
                logger.info(f"Crop identified: {crop_identified} "
                           f"(confidence: {crop_confidence})")
            except (json.JSONDecodeError, ValueError):
                logger.warning("Could not parse crop identification response")
                crop_identified = "unknown"
                crop_confidence = 0.0
                visible_parts = []

        # ── STAGE 2: Disease Diagnosis ──
        logger.info(f"Stage 2: Diagnosing disease for crop='{crop_identified}'...")

        if crop_identified != "unknown" and crop_confidence >= 0.5:
            # We know the crop — do targeted diagnosis
            crop_context = crop_identified
            if additional_context:
                crop_context += f". {additional_context}"

            system_prompt = DISEASE_DIAGNOSIS_PROMPT.format(
                crop_context=crop_context
            )
            user_text = (
                f"This is a {crop_identified} plant. "
                "What disease, pest, or health issue can you see? "
                "Analyze the visible symptoms carefully."
            )
        else:
            # Unknown crop — use general symptom analysis
            logger.info("Crop unknown — using general symptom analysis")
            system_prompt = UNKNOWN_CROP_DIAGNOSIS_PROMPT
            user_text = (
                "The crop type is unknown. Analyze the visible symptoms, "
                "damage patterns, and signs of disease or pest attack. "
                "List all possible causes honestly."
            )

        raw_diagnosis = await _call_vision_model(
            image_base64=image_base64,
            image_media_type=image_media_type,
            system_prompt=system_prompt,
            user_text=user_text,
            temperature=0.2
        )

        diagnosis = _parse_json_response(raw_diagnosis)
        logger.info(f"Diagnosis: {diagnosis.get('detected_issue')} "
                   f"(confidence: {diagnosis.get('confidence')})")

        return {
            "success": True,
            "crop_identified": crop_identified,
            "crop_confidence": crop_confidence,
            "visible_parts": visible_parts,
            "analysis": diagnosis
        }

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error in image analysis: {e}")
        return {
            "success": False,
            "error": "AI model returned an unparseable response. Please try again."
        }
    except Exception as e:
        logger.error(f"Image analysis failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def validate_image(image_bytes: bytes, filename: str) -> tuple[bool, str]:
    """Validates uploaded image before sending to vision model."""
    max_size = 10 * 1024 * 1024
    if len(image_bytes) > max_size:
        return False, "Image too large. Please upload an image smaller than 10MB."

    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    import os
    ext = os.path.splitext(filename.lower())[1]
    if ext not in allowed_extensions:
        return False, f"Unsupported file type '{ext}'. Please upload JPG, PNG, or WebP."

    if len(image_bytes) < 1000:
        return False, "Image too small or corrupted. Please upload a clearer photo."

    return True, ""


def get_media_type(filename: str) -> str:
    """Gets the correct media type from filename."""
    import os
    ext = os.path.splitext(filename.lower())[1]
    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif"
    }
    return media_types.get(ext, "image/jpeg")