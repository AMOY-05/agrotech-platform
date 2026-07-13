from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.services.vision_service import analyze_crop_image, validate_image, get_media_type
from loguru import logger

router = APIRouter()


class ImageAnalysisResponse(BaseModel):
    success: bool
    message: str
    timestamp: datetime
    crop_identified: Optional[str] = None
    crop_confidence: Optional[float] = None
    visual_evidence: Optional[str] = None
    detected_issue: Optional[str] = None
    issue_category: Optional[str] = None
    confidence: Optional[float] = None
    severity: Optional[str] = None
    urgency: Optional[str] = None
    progression_stage: Optional[str] = None
    symptoms_visible: Optional[list] = []
    affected_parts: Optional[list] = []
    spread_risk: Optional[str] = None
    treatment: Optional[str] = None
    prevention: Optional[str] = None
    estimated_yield_impact: Optional[str] = None
    when_to_seek_expert: Optional[str] = None
    possible_causes: Optional[list] = []
    improvement_suggestions: Optional[list] = []
    error: Optional[str] = None


@router.post("/analyze", response_model=ImageAnalysisResponse, tags=["Image Analysis"])
async def analyze_image(
    file: UploadFile = File(..., description="Crop photo to analyze"),
    crop_type: Optional[str] = Form(None, description="Crop type if known"),
    region: Optional[str] = Form(None, description="Farming region")
):
    """
    Analyzes a crop photo for diseases and pests using AI vision.
    Upload a clear photo of the affected crop leaves, stem, or fruit.
    """
    logger.info(f"Image analysis request: file={file.filename}, crop={crop_type}, region={region}")

    try:
        # Read image bytes
        image_bytes = await file.read()

        # Validate image
        is_valid, error_msg = validate_image(image_bytes, file.filename)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        # Build context string
        context_parts = []
        if crop_type:
            context_parts.append(f"The farmer says this is a {crop_type} plant.")
        if region:
            context_parts.append(f"The farm is located in {region}, Nigeria.")
        context = " ".join(context_parts)

        # Get media type
        media_type = get_media_type(file.filename)

        # Analyze image
        result = await analyze_crop_image(
            image_bytes=image_bytes,
            image_media_type=media_type,
            additional_context=context if context else None,
            known_crop_type=crop_type
        )

        if result["success"]:
            analysis = result["analysis"]
            return ImageAnalysisResponse(
                success=True,
                message="Image analysis complete",
                timestamp=datetime.utcnow(),
                crop_identified=result.get("crop_identified"),
                crop_confidence=result.get("crop_confidence"),
                visual_evidence=result.get("visual_evidence"),
                detected_issue=analysis.get("detected_issue"),
                issue_category=analysis.get("issue_category"),
                confidence=float(analysis.get("confidence", 0.0)),
                severity=analysis.get("severity"),
                urgency=analysis.get("urgency"),
                progression_stage=analysis.get("progression_stage"),
                symptoms_visible=analysis.get("symptoms_visible", []),
                affected_parts=analysis.get("affected_parts", []),
                spread_risk=analysis.get("spread_risk"),
                treatment=analysis.get("treatment"),
                prevention=analysis.get("prevention"),
                estimated_yield_impact=analysis.get("estimated_yield_impact"),
                when_to_seek_expert=analysis.get("when_to_seek_expert"),
                possible_causes=analysis.get("possible_causes", [])
            )
        else:
            return ImageAnalysisResponse(
                success=False,
                message=result.get("message", "Analysis failed"),
                timestamp=datetime.utcnow(),
                error=result.get("error"),
                improvement_suggestions=result.get("improvement_suggestions", [])
            )

        analysis = result["analysis"]

        # Handle non-crop images gracefully
        if analysis.get("detected_issue") == "not_a_crop_image":
            return ImageAnalysisResponse(
                success=False,
                message="The uploaded image does not appear to be a crop or plant photo.",
                timestamp=datetime.utcnow(),
                error="Please upload a clear photo of your crop."
            )

        if analysis.get("detected_issue") == "image_unclear":
            return ImageAnalysisResponse(
                success=False,
                message="The image is too blurry or unclear to analyze.",
                timestamp=datetime.utcnow(),
                error="Please take a clearer, well-lit photo of the affected area."
            )

        return ImageAnalysisResponse(
            success=True,
            message="Image analysis complete",
            timestamp=datetime.utcnow(),
            crop_identified=result.get("crop_identified"),
            detected_issue=analysis.get("detected_issue"),
            confidence=float(analysis.get("confidence", 0.0)),
            severity=analysis.get("severity"),
            urgency=analysis.get("urgency"),
            symptoms_visible=analysis.get("symptoms_visible", []),
            treatment=analysis.get("treatment"),
            prevention=analysis.get("prevention"),
            estimated_yield_impact=analysis.get("estimated_yield_impact")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image analysis endpoint failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))