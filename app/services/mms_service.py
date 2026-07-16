"""
Meta MMS (Massively Multilingual Speech) ASR service.
Uses Hugging Face Inference API — no GPU required.
Supports: Yoruba, Hausa, Igbo, and 1000+ other languages.
Falls back to Groq Whisper if MMS unavailable.
"""
import httpx
import io
from app.core.config import settings
from loguru import logger
from typing import Optional

# MMS language codes for Nigerian languages
MMS_LANGUAGE_CODES = {
    "yoruba": "yor",
    "hausa": "hau",
    "igbo": "ibo",
    "english": "eng",
    "pidgin": "eng",  # MMS doesn't have pidgin — use English
    "french": "fra",
}

# Hugging Face MMS model endpoint
MMS_MODEL = "facebook/mms-300m"
HF_INFERENCE_URL = (
    "https://api-inference.huggingface.co/models/facebook/mms-300m"
)


async def transcribe_with_mms(
    audio_bytes: bytes,
    language: str = "english"
) -> Optional[dict]:
    """
    Transcribes audio using Meta MMS via Hugging Face Inference API.
    Returns transcription dict or None if failed.
    """
    if not settings.huggingface_token:
        logger.warning("Hugging Face token not configured — skipping MMS")
        return None

    lang_code = MMS_LANGUAGE_CODES.get(language.lower(), "eng")
    logger.info(
        f"Transcribing with Meta MMS: language={language} "
        f"(code={lang_code}), audio={len(audio_bytes)} bytes"
    )

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                HF_INFERENCE_URL,
                headers={
                    "Authorization": f"Bearer {settings.huggingface_token}",
                    "Content-Type": "audio/wav",
                },
                params={"lang_id": lang_code},
                content=audio_bytes
            )

            if response.status_code == 200:
                result = response.json()
                text = result.get("text", "").strip()

                if text:
                    logger.info(f"MMS transcription: '{text[:80]}'")
                    return {
                        "success": True,
                        "text": text,
                        "language": language,
                        "model": "Meta MMS",
                        "confidence": result.get("confidence", None)
                    }
                else:
                    logger.warning("MMS returned empty transcription")
                    return None

            elif response.status_code == 503:
                logger.warning("MMS model loading — will retry with Whisper")
                return None

            else:
                logger.error(
                    f"MMS API error: {response.status_code} — {response.text[:200]}"
                )
                return None

    except httpx.TimeoutException:
        logger.warning("MMS request timed out — falling back to Whisper")
        return None
    except Exception as e:
        logger.error(f"MMS transcription failed: {e}")
        return None


async def transcribe_with_whisper_fallback(
    audio_bytes: bytes,
    filename: str,
    language_hint: Optional[str] = None
) -> dict:
    """Falls back to Groq Whisper if MMS fails."""
    from groq import Groq
    from app.core.config import settings as app_settings

    client = Groq(api_key=app_settings.groq_api_key)
    logger.info("Using Groq Whisper as fallback ASR")

    try:
        audio_file = (filename, io.BytesIO(audio_bytes), "audio/ogg")

        params = {
            "file": audio_file,
            "model": "whisper-large-v3",
            "response_format": "verbose_json",
            "temperature": 0.0
        }

        if language_hint and language_hint not in ("pidgin",):
            lang_map = {
                "yoruba": "yo",
                "hausa": "ha",
                "igbo": "ig",
                "english": "en"
            }
            lang_code = lang_map.get(language_hint.lower())
            if lang_code:
                params["language"] = lang_code

        response = client.audio.transcriptions.create(**params)
        text = response.text.strip()
        detected = getattr(response, "language", language_hint or "english")

        return {
            "success": True,
            "text": text,
            "language": detected,
            "model": "Groq Whisper Large v3"
        }

    except Exception as e:
        logger.error(f"Whisper fallback also failed: {e}")
        return {
            "success": False,
            "text": "",
            "error": str(e),
            "model": "none"
        }


async def smart_transcribe(
    audio_bytes: bytes,
    filename: str,
    preferred_language: str = "english"
) -> dict:
    """
    Smart transcription that routes to the best available model:
    1. Meta MMS for Yoruba, Hausa, Igbo (best African language support)
    2. Groq Whisper for English, Pidgin, or as fallback

    This gives investors confidence we use state-of-the-art multilingual AI.
    """
    language_lower = preferred_language.lower()

    # Use MMS for native Nigerian languages
    if language_lower in ("yoruba", "hausa", "igbo"):
        logger.info(f"Routing to Meta MMS for {preferred_language}")
        mms_result = await transcribe_with_mms(audio_bytes, preferred_language)

        if mms_result and mms_result.get("success"):
            return {
                "success": True,
                "transcribed_text": mms_result["text"],
                "detected_language": preferred_language,
                "model_used": "Meta MMS (facebook/mms-300m)",
                "duration_seconds": None
            }
        else:
            logger.warning(
                f"MMS failed for {preferred_language} — falling back to Whisper"
            )

    # Use Whisper for English, Pidgin, or as fallback
    logger.info(f"Using Groq Whisper for {preferred_language}")
    whisper_result = await transcribe_with_whisper_fallback(
        audio_bytes, filename, preferred_language
    )

    return {
        "success": whisper_result.get("success", False),
        "transcribed_text": whisper_result.get("text", ""),
        "detected_language": whisper_result.get("language", preferred_language),
        "model_used": whisper_result.get("model", "Groq Whisper Large v3"),
        "duration_seconds": None,
        "error": whisper_result.get("error")
    }