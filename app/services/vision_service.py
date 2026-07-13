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
You are an expert botanist and agronomist specializing in West African and 
Nigerian crop farming systems.

Analyze this image carefully for visual identification of the crop/plant.

Look specifically for:
- Leaf shape, size, texture, color, and venation pattern
- Stem characteristics (thickness, color, surface texture)
- Fruit/seed/root if visible
- Growth pattern and plant architecture
- Any distinctive markers of Nigerian/West African crop varieties

Common Nigerian crops to consider:
Cereals: maize, rice, sorghum, millet, wheat
Roots/Tubers: cassava, yam, cocoyam, sweet potato, potato
Legumes: cowpea, soybean, groundnut, bambara nut
Vegetables: tomato, pepper, okra, garden egg, onion, waterleaf, ugu
Fruits: plantain, banana, mango, pineapple, papaya, coconut, watermelon
Cash crops: cocoa, palm oil, rubber, cotton, sugarcane, ginger, sesame

Respond with ONLY this JSON:
{
  "crop_identified": "specific crop common name or 'unknown'",
  "crop_confidence": 0.85,
  "crop_family": "plant family",
  "visible_parts": ["leaf", "stem", "fruit", "root", "flower", "seed"],
  "visual_evidence": "specific visual features that led to this identification",
  "identification_notes": "any uncertainty or alternative possibilities"
}

CRITICAL RULES:
- If confidence is below 0.5, set crop_identified to 'unknown'
- NEVER guess based on disease pattern alone
- Base identification ONLY on visible plant morphology
- Return ONLY the JSON. No extra text.
"""

DISEASE_DIAGNOSIS_PROMPT = """
You are a senior agricultural pathologist with 20 years experience in 
Nigerian and West African crop disease management.

The farmer has sent a photo of their {crop_context} showing signs of 
possible disease, pest damage, or nutritional deficiency.

Analyze the image systematically:
1. What symptoms are visible? (spots, lesions, wilting, discoloration, deformation)
2. What is the distribution pattern? (scattered, clustered, whole plant, specific parts)
3. What stage of progression? (early/developing/advanced/severe)
4. What is the most likely cause based on visual evidence?

Consider these common Nigerian crop problems:
- Fungal: early blight, late blight, leaf spot, anthracnose, rust, powdery mildew
- Bacterial: bacterial wilt, bacterial spot, bacterial blight
- Viral: mosaic virus, streak virus, leaf curl virus
- Pest: stem borer, aphids, whitefly, spider mite, thrips, caterpillar damage
- Nutritional: nitrogen deficiency (yellowing), iron deficiency (interveinal chlorosis)
- Environmental: drought stress, waterlogging, sunscald

Respond with ONLY this JSON:
{{
  "detected_issue": "specific disease/pest/condition name (common + scientific name)",
  "issue_category": "fungal/bacterial/viral/pest/nutritional/environmental",
  "confidence": 0.85,
  "severity": "early/moderate/severe",
  "urgency": "low/medium/high/critical",
  "progression_stage": "early/developing/advanced",
  "symptoms_visible": [
    "specific symptom 1 visible in image",
    "specific symptom 2 visible in image"
  ],
  "affected_parts": ["leaf", "stem", "fruit", "root"],
  "spread_risk": "low/medium/high",
  "treatment": {{
    "immediate": "what to do in next 24-48 hours",
    "products": [
      {{
        "name": "specific product name available in Nigeria",
        "type": "fungicide/insecticide/bactericide/fertilizer",
        "application": "how to apply"
      }}
    ],
    "cultural": "farming practice changes to make"
  }},
  "prevention": "specific prevention measures for next season",
  "estimated_yield_impact": "X-Y% yield loss if untreated",
  "when_to_seek_expert": "conditions under which to contact agricultural extension officer"
}}

RULES:
- confidence between 0.0 and 1.0
- urgency: low=can wait a week, medium=treat within 3 days, high=treat today, critical=may lose entire crop
- If confidence < 0.5, list top 2-3 possibilities in detected_issue
- Products must be realistically available in Nigerian agro-chemical stores
- Return ONLY the JSON. No extra text.
"""

UNKNOWN_CROP_DIAGNOSIS_PROMPT = """
You are a senior agricultural pathologist specializing in West African crops.

The crop type cannot be confidently identified from this image.
Focus EXCLUSIVELY on the visible symptoms, damage patterns, and disease signs.

Analyze what you can see:
- Color changes (yellowing, browning, blackening, purple/red discoloration)
- Physical damage (holes, lesions, spots, pustules, mold, rot)
- Structural changes (wilting, curling, stunting, distortion)
- Presence of organisms (insects, eggs, webbing, fungal growth)

Respond with ONLY this JSON:
{
  "detected_issue": "symptom-based description of the problem",
  "issue_category": "fungal/bacterial/viral/pest/nutritional/environmental/unknown",
  "confidence": 0.45,
  "severity": "early/moderate/severe",
  "urgency": "low/medium/high/critical",
  "symptoms_visible": [
    "specific symptom 1 you can see",
    "specific symptom 2 you can see"
  ],
  "possible_causes": [
    "most likely cause based on symptoms",
    "second possibility",
    "third possibility"
  ],
  "treatment": {
    "immediate": "general immediate action regardless of crop type",
    "products": [
      {
        "name": "broad-spectrum product available in Nigeria",
        "type": "fungicide/insecticide/general",
        "application": "general application guidance"
      }
    ],
    "cultural": "general good farming practice"
  },
  "prevention": "general prevention advice",
  "estimated_yield_impact": "varies by crop and disease stage",
  "recommendation": "Take this photo to your nearest NALDA or agricultural extension office for precise identification. Also send a clearer close-up photo of the most affected area."
}

Return ONLY the JSON. No extra text.
"""


# Add this new prompt for photo quality assessment
PHOTO_QUALITY_PROMPT = """
You are assessing whether a farm photo is suitable for crop disease diagnosis.

Check:
1. Is this a photo of a plant/crop? (yes/no)
2. Is the affected area clearly visible? (yes/no)  
3. Is the image sharp enough to see symptoms? (yes/no)
4. Is there sufficient lighting? (yes/no)

Respond with ONLY this JSON:
{
  "is_crop_photo": true,
  "is_usable": true,
  "quality_issues": [],
  "improvement_suggestions": []
}

Examples of quality_issues: "too blurry", "too dark", "affected area not visible", "too far away"
Examples of improvement_suggestions: "move closer to affected leaves", "take photo in natural light", "focus on the spots/lesions"

Return ONLY the JSON. No extra text.
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
    Enhanced two-stage crop image analysis with quality check.
    """
    logger.info(f"Analyzing crop image: {len(image_bytes)} bytes, "
                f"known_crop={known_crop_type}")

    try:
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        # ── Stage 0: Photo Quality Check ──
        logger.info("Stage 0: Checking photo quality...")
        try:
            raw_quality = await _call_vision_model(
                image_base64=image_base64,
                image_media_type=image_media_type,
                system_prompt=PHOTO_QUALITY_PROMPT,
                user_text="Is this photo suitable for crop disease diagnosis?",
                temperature=0.1
            )
            quality = _parse_json_response(raw_quality)

            if not quality.get("is_crop_photo", True):
                return {
                    "success": False,
                    "error": "not_a_crop_image",
                    "message": "This doesn't appear to be a crop or plant photo. Please upload a clear photo of your crop.",
                    "improvement_suggestions": []
                }

            if not quality.get("is_usable", True):
                issues = quality.get("quality_issues", [])
                suggestions = quality.get("improvement_suggestions", [])
                return {
                    "success": False,
                    "error": "poor_photo_quality",
                    "message": f"Photo quality is too low for accurate diagnosis. Issues: {', '.join(issues)}",
                    "improvement_suggestions": suggestions
                }

        except Exception as e:
            logger.warning(f"Quality check failed (non-critical): {e}")

        # ── Stage 1: Crop Identification ──
        if known_crop_type:
            crop_identified = known_crop_type.lower().strip()
            crop_confidence = 1.0
            visible_parts = []
            visual_evidence = f"Crop type provided by farmer: {known_crop_type}"
            logger.info(f"Using farmer-provided crop type: {crop_identified}")
        else:
            logger.info("Stage 1: Identifying crop...")
            raw_id = await _call_vision_model(
                image_base64=image_base64,
                image_media_type=image_media_type,
                system_prompt=CROP_IDENTIFICATION_PROMPT,
                user_text=(
                    "Identify the crop in this image. Look carefully at leaf shape, "
                    "stem structure, and any visible fruits or roots. "
                    "Be honest if you cannot identify it confidently."
                ),
                temperature=0.1
            )

            try:
                id_result = _parse_json_response(raw_id)
                crop_identified = id_result.get(
                    "crop_identified", "unknown"
                ).lower().strip()
                crop_confidence = float(id_result.get("crop_confidence", 0.0))
                visible_parts = id_result.get("visible_parts", [])
                visual_evidence = id_result.get("visual_evidence", "")
                identification_notes = id_result.get("identification_notes", "")

                logger.info(
                    f"Crop identified: '{crop_identified}' "
                    f"(confidence: {crop_confidence:.0%})"
                )

                # Reject low-confidence identifications
                if crop_confidence < 0.5:
                    crop_identified = "unknown"
                    logger.info("Confidence too low — treating as unknown crop")

            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Could not parse crop ID: {e}")
                crop_identified = "unknown"
                crop_confidence = 0.0
                visible_parts = []
                visual_evidence = ""

        # ── Stage 2: Disease Diagnosis ──
        logger.info(f"Stage 2: Diagnosing for crop='{crop_identified}'...")

        if crop_identified != "unknown" and crop_confidence >= 0.5:
            crop_context = crop_identified
            if additional_context:
                crop_context += f". Additional context: {additional_context}"

            system_prompt = DISEASE_DIAGNOSIS_PROMPT.format(
                crop_context=crop_context
            )
            user_text = (
                f"This is a {crop_identified} plant. "
                "Analyze all visible symptoms carefully and provide a diagnosis. "
                "Focus on what you can actually see in the image."
            )
        else:
            system_prompt = UNKNOWN_CROP_DIAGNOSIS_PROMPT
            user_text = (
                "The crop type could not be identified confidently. "
                "Analyze all visible symptoms, damage patterns, and signs of disease. "
                "Describe what you see and list possible causes."
            )

        raw_diagnosis = await _call_vision_model(
            image_base64=image_base64,
            image_media_type=image_media_type,
            system_prompt=system_prompt,
            user_text=user_text,
            temperature=0.2
        )

        diagnosis = _parse_json_response(raw_diagnosis)

        # Flatten treatment if it's nested
        treatment_raw = diagnosis.get("treatment", {})
        if isinstance(treatment_raw, dict):
            immediate = treatment_raw.get("immediate", "")
            products = treatment_raw.get("products", [])
            cultural = treatment_raw.get("cultural", "")
            products_str = "; ".join(
                f"{p.get('name', '')} ({p.get('type', '')}): {p.get('application', '')}"
                for p in products if isinstance(p, dict)
            )
            treatment_text = f"{immediate}"
            if products_str:
                treatment_text += f"\n\nProducts available in Nigeria: {products_str}"
            if cultural:
                treatment_text += f"\n\nFarming practices: {cultural}"
        else:
            treatment_text = str(treatment_raw)

        logger.info(
            f"Diagnosis: {diagnosis.get('detected_issue')} "
            f"(confidence: {diagnosis.get('confidence')}, "
            f"urgency: {diagnosis.get('urgency')})"
        )

        return {
            "success": True,
            "crop_identified": crop_identified,
            "crop_confidence": crop_confidence,
            "visible_parts": visible_parts,
            "visual_evidence": visual_evidence,
            "analysis": {
                "detected_issue": diagnosis.get("detected_issue", "Unknown"),
                "issue_category": diagnosis.get("issue_category", "unknown"),
                "confidence": float(diagnosis.get("confidence", 0.0)),
                "severity": diagnosis.get("severity", "unknown"),
                "urgency": diagnosis.get("urgency", "medium"),
                "progression_stage": diagnosis.get("progression_stage", "unknown"),
                "symptoms_visible": diagnosis.get("symptoms_visible", []),
                "affected_parts": diagnosis.get("affected_parts", []),
                "spread_risk": diagnosis.get("spread_risk", "unknown"),
                "treatment": treatment_text,
                "prevention": diagnosis.get("prevention", ""),
                "estimated_yield_impact": diagnosis.get(
                    "estimated_yield_impact", ""
                ),
                "when_to_seek_expert": diagnosis.get("when_to_seek_expert", ""),
                "possible_causes": diagnosis.get("possible_causes", [])
            }
        }

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error in image analysis: {e}")
        return {
            "success": False,
            "error": "Could not parse AI response. Please try again."
        }
    except Exception as e:
        logger.error(f"Image analysis failed: {e}")
        return {
            "success": False,
            "error": str(e)
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