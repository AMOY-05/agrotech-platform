from fastapi import APIRouter, Request
from app.services.telegram_service import (
    send_message,
    send_typing_action,
    download_telegram_file,
    parse_farmer_id,
    _is_language_command
)
from app.services.voice_service import (
    translate_response_to_language,
    process_voice_message
)
from app.agent.agent import run_agent
from loguru import logger
import json

router = APIRouter()

# In-memory language prefs (Redis in production)
_telegram_prefs: dict = {}

WELCOME_MESSAGE = """🌾 *Welcome to AgroTech Intelligence!*

I'm AgroBot, your AI farming assistant for Nigerian farmers.

I can help you with:
🐛 *Pest & disease detection*
📊 *Crop yield prediction*
💰 *Market price forecasting*
📍 *Nearby agro-input stores*
🌦️ *Weather-based farming advice*

Just type your farming question!

🌐 *Change language:*
/language yoruba
/language hausa
/language igbo
/language pidgin
/language english

🎤 Send a voice note and I'll understand it
📸 Send a crop photo and I'll analyze it

What would you like to know? 🌱"""

HELP_MESSAGE = """*AgroBot Commands:*

/start - Welcome message
/help - Show this help
/language [lang] - Change response language
/status - Check your farm context

Just type your question naturally — no commands needed!"""


def _get_pref(user_id: int) -> str:
    return _telegram_prefs.get(user_id, {}).get("language", "english")


def _set_pref(user_id: int, language: str):
    if user_id not in _telegram_prefs:
        _telegram_prefs[user_id] = {}
    _telegram_prefs[user_id]["language"] = language


@router.post("/webhook", tags=["Telegram"])
async def telegram_webhook(request: Request):
    """
    Receives all Telegram updates and routes them appropriately.
    Handles text messages, voice notes, and photos.
    """
    try:
        body = await request.json()
        logger.info(f"Telegram update: {json.dumps(body)[:200]}")

        message = body.get("message", {})
        if not message:
            return {"status": "ok"}

        chat_id = message.get("chat", {}).get("id")
        user_id = message.get("from", {}).get("id")
        user_name = message.get("from", {}).get("first_name", "Farmer")
        farmer_id = parse_farmer_id(user_id)
        preferred_language = _get_pref(user_id)

        if not chat_id:
            return {"status": "ok"}

        # ── Text Message ──
        if "text" in message:
            text = message["text"].strip()

            # Commands
            if text == "/start":
                await send_message(chat_id, WELCOME_MESSAGE)
                return {"status": "ok"}

            if text == "/help":
                await send_message(chat_id, HELP_MESSAGE)
                return {"status": "ok"}

            if text == "/status":
                from app.agent.memory import get_session
                session = get_session(farmer_id)
                ctx = session.context
                filled = {k: v for k, v in ctx.items() if v}
                if filled:
                    status_text = "📋 *Your Farm Context:*\n"
                    for k, v in filled.items():
                        status_text += f"• {k.replace('_', ' ').title()}: {v}\n"
                else:
                    status_text = "No farm context saved yet. Tell me about your farm!"
                await send_message(chat_id, status_text)
                return {"status": "ok"}

            # Language command
            new_lang = _is_language_command(text)
            if new_lang:
                _set_pref(user_id, new_lang)
                confirmations = {
                    "yoruba": f"✅ Ẹ káàbọ̀ {user_name}! Mo ti ṣeto èdè rẹ sí Yorùbá.",
                    "hausa": f"✅ Sannu {user_name}! Na saita harshenka zuwa Hausa.",
                    "igbo": f"✅ Ndewo {user_name}! Ahaziela asụsụ gị na Igbo.",
                    "pidgin": f"✅ How far {user_name}! I don set your language to Pidgin.",
                    "english": f"✅ Language set to English, {user_name}!"
                }
                await send_message(
                    chat_id,
                    confirmations.get(new_lang, f"✅ Language set to {new_lang}!")
                )
                return {"status": "ok"}

            # Regular farming question
            await send_typing_action(chat_id)
            await _handle_text(chat_id, farmer_id, text, preferred_language)

        # ── Voice Note ──
        elif "voice" in message or "audio" in message:
            media = message.get("voice") or message.get("audio")
            file_id = media.get("file_id")
            if file_id:
                await send_message(chat_id, "🎤 _Processing your voice note..._")
                await _handle_voice(
                    chat_id, farmer_id, file_id, preferred_language
                )

        # ── Photo ──
        elif "photo" in message:
            # Telegram sends photos in multiple sizes — take the largest
            photos = message["photo"]
            largest_photo = max(photos, key=lambda p: p.get("file_size", 0))
            file_id = largest_photo.get("file_id")
            caption = message.get("caption", "")
            if file_id:
                await send_message(chat_id, "📸 _Analyzing your crop photo..._")
                await _handle_photo(
                    chat_id, farmer_id, file_id, caption, preferred_language
                )

        # ── Document (audio file sent as document) ──
        elif "document" in message:
            doc = message["document"]
            mime = doc.get("mime_type", "")
            if "audio" in mime or "ogg" in mime:
                file_id = doc.get("file_id")
                if file_id:
                    await send_message(chat_id, "🎤 _Processing your voice note..._")
                    await _handle_voice(
                        chat_id, farmer_id, file_id, preferred_language
                    )
            else:
                await send_message(
                    chat_id,
                    "I can analyze text, voice notes, and crop photos. "
                    "Please send one of those! 🌾"
                )

        else:
            await send_message(
                chat_id,
                "I can understand text messages, voice notes 🎤, and crop photos 📸. "
                "What would you like help with?"
            )

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Telegram webhook error: {e}")
        return {"status": "error"}


async def _handle_text(
    chat_id: int,
    farmer_id: str,
    text: str,
    preferred_language: str
):
    """Processes text through agent and sends reply."""
    try:
        result = await run_agent(
            user_message=text,
            farmer_id=farmer_id
        )

        reply = result.get("reply", "")
        tools_used = result.get("tools_used", [])

        if preferred_language != "english":
            reply = await translate_response_to_language(reply, preferred_language)

        # Add tool badges
        if tools_used:
            tool_labels = {
                "detect_pest_disease": "🐛 Pest Analysis",
                "forecast_price": "💰 Price Forecast",
                "predict_yield": "📊 Yield Prediction",
                "find_nearby_stores": "📍 Store Search"
            }
            tools_text = " | ".join(tool_labels.get(t, t) for t in tools_used)
            reply = f"{reply}\n\n_{tools_text}_"

        await send_message(chat_id, reply)

    except Exception as e:
        logger.error(f"Text handling failed: {e}")
        await send_message(
            chat_id,
            "⚠️ Sorry, I had trouble with that. Please try again."
        )


async def _handle_voice(
    chat_id: int,
    farmer_id: str,
    file_id: str,
    preferred_language: str
):
    """Downloads and processes a voice note."""
    try:
        audio_bytes = await download_telegram_file(file_id)
        if not audio_bytes:
            await send_message(
                chat_id,
                "⚠️ Could not download your voice note. Please try again."
            )
            return

        result = await process_voice_message(
            audio_bytes=audio_bytes,
            filename="voice.ogg",
            farmer_id=farmer_id,
            preferred_language=preferred_language
        )

        if result["success"]:
            transcribed = result.get("transcribed_text", "")
            reply = result.get("reply", "")
            full_reply = f"🎤 _You said: \"{transcribed}\"_\n\n{reply}"
            await send_message(chat_id, full_reply)
        else:
            await send_message(
                chat_id,
                f"⚠️ Could not process voice note: "
                f"{result.get('error', 'Please try again.')}"
            )

    except Exception as e:
        logger.error(f"Voice handling failed: {e}")
        await send_message(
            chat_id,
            "⚠️ Voice processing failed. Please send a text message instead."
        )


async def _handle_photo(
    chat_id: int,
    farmer_id: str,
    file_id: str,
    caption: str,
    preferred_language: str
):
    """Downloads and analyzes a crop photo."""
    from app.services.vision_service import analyze_crop_image

    try:
        image_bytes = await download_telegram_file(file_id)
        if not image_bytes:
            await send_message(
                chat_id,
                "⚠️ Could not download your photo. Please try again."
            )
            return

        crop_type = caption.strip() if caption else None

        result = await analyze_crop_image(
            image_bytes=image_bytes,
            image_media_type="image/jpeg",
            additional_context=f"Nigerian farmer. {caption}" if caption else None,
            known_crop_type=crop_type
        )

        if result["success"]:
            analysis = result["analysis"]
            crop = result.get("crop_identified", "unknown")
            issue = analysis.get("detected_issue", "Unknown")
            confidence = analysis.get("confidence", 0)
            severity = analysis.get("severity", "unknown")
            urgency = analysis.get("urgency", "medium")
            treatment = analysis.get("treatment", "")
            prevention = analysis.get("prevention", "")
            yield_impact = analysis.get("estimated_yield_impact", "")
            symptoms = analysis.get("symptoms_visible", [])

            urgency_emoji = {
                "low": "🟢", "medium": "🟡", "high": "🔴"
            }.get(urgency, "🟡")

            symptoms_text = "\n".join(f"• {s}" for s in symptoms) if symptoms else ""

            reply = (
                f"📸 *Crop Photo Analysis*\n\n"
                f"🌱 *Crop:* {crop.title()}\n"
                f"🔍 *Issue:* {issue}\n"
                f"📊 *Confidence:* {confidence:.0%}\n"
                f"⚠️ *Severity:* {severity.title()}\n"
                f"🚨 *Urgency:* {urgency_emoji} {urgency.title()}\n"
            )

            if symptoms_text:
                reply += f"\n*Visible Symptoms:*\n{symptoms_text}\n"

            reply += (
                f"\n💊 *Treatment:*\n{treatment}\n\n"
                f"🛡️ *Prevention:*\n{prevention}\n\n"
                f"📉 *Yield Impact if Untreated:* {yield_impact}"
            )

            if preferred_language != "english":
                reply = await translate_response_to_language(
                    reply, preferred_language
                )

            await send_message(chat_id, reply)
        else:
            await send_message(
                chat_id,
                "⚠️ Could not analyze the photo. "
                "Please send a clearer image of the affected crop area.\n\n"
                "_Tip: Make sure the affected leaves or stems are clearly visible._"
            )

    except Exception as e:
        logger.error(f"Photo handling failed: {e}")
        await send_message(
            chat_id,
            "⚠️ Photo analysis failed. Please try again."
        )


@router.post("/webhook", tags=["Telegram"])
async def telegram_webhook(request: Request):
    # ngrok free tier fix
    headers = dict(request.headers)
    logger.info(f"Webhook headers: {headers.get('x-forwarded-for', 'no-forwarded')}")
    logger.info(f"ngrok bypass: {headers.get('ngrok-skip-browser-warning', 'not-set')}")

@router.get("/set-webhook", tags=["Telegram"])
async def setup_webhook(webhook_url: str):
    """
    Convenience endpoint to set the Telegram webhook.
    Call this once after deployment with your public URL.
    Usage: GET /api/v1/telegram/set-webhook?webhook_url=https://your-domain.com
    """
    from app.services.telegram_service import set_webhook
    success = await set_webhook(webhook_url)
    if success:
        return {"status": "success", "webhook_url": webhook_url}
    return {"status": "failed"}


@router.get("/delete-webhook", tags=["Telegram"])
async def remove_webhook():
    """Removes the webhook (switches to polling mode for local testing)."""
    from app.services.telegram_service import delete_webhook
    success = await delete_webhook()
    return {"status": "success" if success else "failed"}