from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.services.voice_service import process_voice_message, validate_audio
from loguru import logger

router = APIRouter()


class VoiceResponse(BaseModel):
    success: bool
    message: str
    timestamp: datetime
    transcribed_text: Optional[str] = None
    english_text: Optional[str] = None
    detected_language: Optional[str] = None
    reply: Optional[str] = None
    tools_used: Optional[List[str]] = []
    session_context: Optional[dict] = {}
    error: Optional[str] = None


@router.post("/process", response_model=VoiceResponse, tags=["Voice Notes"])
async def process_voice(
    file: UploadFile = File(..., description="Voice note audio file"),
    farmer_id: str = Form(..., description="Farmer's unique ID"),
    preferred_language: str = Form("english", description="Farmer's preferred language"),
    crop_context: Optional[str] = Form(None, description="Current crop context if known")
):
    """
    Process a voice note from a farmer.
    Accepts audio in any Nigerian language, transcribes it,
    processes it through the AI agent, and returns a response
    in the farmer's preferred language.
    """
    logger.info(f"Voice note received: farmer={farmer_id}, "
                f"language={preferred_language}, file={file.filename}")

    try:
        # Read audio
        audio_bytes = await file.read()

        # Validate
        is_valid, error_msg = validate_audio(audio_bytes, file.filename)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        # Process through full pipeline
        result = await process_voice_message(
            audio_bytes=audio_bytes,
            filename=file.filename,
            farmer_id=farmer_id,
            preferred_language=preferred_language,
            crop_context=crop_context
        )

        if not result["success"]:
            return VoiceResponse(
                success=False,
                message="Voice processing failed",
                timestamp=datetime.utcnow(),
                error=result.get("error")
            )

        return VoiceResponse(
            success=True,
            message="Voice note processed successfully",
            timestamp=datetime.utcnow(),
            transcribed_text=result["transcribed_text"],
            english_text=result.get("english_text"),
            detected_language=result.get("detected_language"),
            reply=result["reply"],
            tools_used=result.get("tools_used", []),
            session_context=result.get("session_context", {})
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice processing endpoint failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))