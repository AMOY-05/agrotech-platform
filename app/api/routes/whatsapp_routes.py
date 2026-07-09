from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import Response
from typing import Optional
from app.agent.agent import run_agent
from app.services.whatsapp_service import (
    send_whatsapp_message,
    parse_whatsapp_number,
    detect_language_from_number
)
from app.services.voice_service import translate_response_to_language
from app.models.db.database import get_db
from loguru import logger
import hashlib

router = APIRouter()

# Track active WhatsApp sessions language preferences
# In production this would be in Redis/DB
_whatsapp_language_prefs: dict = {}

WELCOME_MESSAGE = """🌾 *Welcome to AgroTech!*

I'm AgroBot, your AI farming assistant. I can help you with:

🐛 Pest & disease detection
📊 Crop yield prediction  
💰 Market price forecasting
📍 Nearby agro-input stores
🌦️ Weather-based farming advice

Just send me your question in *English, Yoruba, Hausa, Igbo, or Pidgin*!

To set your language, send:
*language: yoruba* (or hausa, igbo, pidgin, english)

What would you like to know? 🌱"""


def _get_farmer_language(whatsapp_number: str) -> str:
    """Gets the farmer's preferred language for this WhatsApp number."""
    return _whatsapp_language_prefs.get(whatsapp_number, "english")


def _set_farmer_language(whatsapp_number: str, language: str):
    """Sets the farmer's preferred language."""
    _whatsapp_language_prefs[whatsapp_number] = language
    logger.info(f"WhatsApp {whatsapp_number} language set to {language}")


def _is_language_command(message: str) -> Optional[str]:
    """
    Detects if farmer is setting their language preference.
    e.g. "language: yoruba" or "set language hausa"
    """
    message_lower = message.lower().strip()
    languages = ["english", "yoruba", "hausa", "igbo", "pidgin"]

    for lang in languages:
        if f"language: {lang}" in message_lower or \
           f"language {lang}" in message_lower or \
           message_lower == lang:
            return lang
    return None


def _is_greeting(message: str) -> bool:
    """Detects greeting messages."""
    greetings = ["hi", "hello", "hey", "start", "help",
                 "howdy", "good morning", "good afternoon",
                 "ẹ káàárọ̀", "ẹ káàbọ̀", "sannu", "ndewo"]
    return message.lower().strip() in greetings


@router.post("/webhook", tags=["WhatsApp"])
async def whatsapp_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
    NumMedia: Optional[str] = Form("0"),
    MediaUrl0: Optional[str] = Form(None),
    MediaContentType0: Optional[str] = Form(None)
):
    """
    Twilio WhatsApp webhook endpoint.
    Receives messages from farmers and returns AI responses.
    """
    whatsapp_number = From
    message_body = Body.strip()
    farmer_id = parse_whatsapp_number(whatsapp_number)

    logger.info(f"WhatsApp message from {whatsapp_number} ({farmer_id}): "
                f"'{message_body[:80]}'")

    try:
        # --- Handle greeting/start ---
        if _is_greeting(message_body):
            await send_whatsapp_message(whatsapp_number, WELCOME_MESSAGE)
            return Response(content="", media_type="text/plain")

        # --- Handle language setting ---
        new_language = _is_language_command(message_body)
        if new_language:
            _set_farmer_language(whatsapp_number, new_language)
            lang_confirmations = {
                "yoruba": "✅ Mo ti ṣeto èdè rẹ sí Yorùbá!",
                "hausa": "✅ Na saita harshenka zuwa Hausa!",
                "igbo": "✅ Ahaziela asụsụ gị na Igbo!",
                "pidgin": "✅ I don set your language to Pidgin!",
                "english": "✅ Language set to English!"
            }
            confirmation = lang_confirmations.get(new_language,
                                                  f"✅ Language set to {new_language}!")
            await send_whatsapp_message(whatsapp_number, confirmation)
            return Response(content="", media_type="text/plain")

        # --- Handle voice note (audio media) ---
        if NumMedia and int(NumMedia) > 0 and MediaUrl0:
            content_type = MediaContentType0 or ""
            if "audio" in content_type:
                await _handle_voice_whatsapp(
                    whatsapp_number, farmer_id, MediaUrl0, content_type
                )
                return Response(content="", media_type="text/plain")

        # --- Handle regular text message ---
        preferred_language = _get_farmer_language(whatsapp_number)

        # Send typing indicator (acknowledgment)
        await send_whatsapp_message(
            whatsapp_number,
            "⏳ AgroBot is thinking..."
        )

        # Run through agent
        result = await run_agent(
            user_message=message_body,
            farmer_id=farmer_id,
            crop_context=None
        )

        reply = result.get("reply", "")
        tools_used = result.get("tools_used", [])

        # Translate if needed
        if preferred_language != "english":
            reply = await translate_response_to_language(
                response_text=reply,
                target_language=preferred_language
            )

        # Add tool usage context for transparency
        if tools_used:
            tool_labels = {
                "detect_pest_disease": "🐛 Pest Analysis",
                "forecast_price": "💰 Price Forecast",
                "predict_yield": "📊 Yield Prediction",
                "find_nearby_stores": "📍 Store Search"
            }
            tools_text = " | ".join(
                tool_labels.get(t, t) for t in tools_used
            )
            reply = f"{reply}\n\n_{tools_text}_"

        await send_whatsapp_message(whatsapp_number, reply)
        logger.info(f"WhatsApp reply sent to {whatsapp_number}")

        return Response(content="", media_type="text/plain")

    except Exception as e:
        logger.error(f"WhatsApp webhook error: {e}")
        error_msg = (
            "⚠️ Sorry, I encountered an error processing your message. "
            "Please try again."
        )
        await send_whatsapp_message(whatsapp_number, error_msg)
        return Response(content="", media_type="text/plain")


async def _handle_voice_whatsapp(
    whatsapp_number: str,
    farmer_id: str,
    media_url: str,
    content_type: str
):
    """Handles voice notes sent via WhatsApp."""
    import httpx
    from app.services.voice_service import process_voice_message

    preferred_language = _get_farmer_language(whatsapp_number)

    try:
        await send_whatsapp_message(
            whatsapp_number,
            "🎤 Processing your voice note..."
        )

        # Download audio from Twilio
        from app.core.config import settings
        async with httpx.AsyncClient(
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            timeout=30.0
        ) as client:
            audio_response = await client.get(media_url)
            audio_bytes = audio_response.content

        # Determine filename from content type
        ext_map = {
            "audio/ogg": "voice.ogg",
            "audio/mpeg": "voice.mp3",
            "audio/mp4": "voice.mp4",
            "audio/amr": "voice.amr"
        }
        filename = ext_map.get(content_type, "voice.ogg")

        # Process through voice pipeline
        result = await process_voice_message(
            audio_bytes=audio_bytes,
            filename=filename,
            farmer_id=farmer_id,
            preferred_language=preferred_language
        )

        if result["success"]:
            transcribed = result.get("transcribed_text", "")
            reply = result.get("reply", "")

            full_reply = (
                f"🎤 _You said: \"{transcribed}\"_\n\n"
                f"{reply}"
            )
            await send_whatsapp_message(whatsapp_number, full_reply)
        else:
            await send_whatsapp_message(
                whatsapp_number,
                f"⚠️ Could not process voice note: "
                f"{result.get('error', 'Unknown error')}"
            )

    except Exception as e:
        logger.error(f"WhatsApp voice handling failed: {e}")
        await send_whatsapp_message(
            whatsapp_number,
            "⚠️ Could not process your voice note. Please try sending a text message."
        )


@router.get("/webhook", tags=["WhatsApp"])
async def whatsapp_webhook_verify(request: Request):
    """
    Webhook verification endpoint for Twilio.
    Not needed for Twilio (unlike Meta direct API) but useful for health checks.
    """
    return {"status": "WhatsApp webhook active"}