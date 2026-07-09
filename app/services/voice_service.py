import io
from groq import Groq
from app.core.config import settings
from app.services.llm_service import ask_llm
from loguru import logger
from typing import Optional

client = Groq(api_key=settings.groq_api_key)

# Supported languages with their Whisper language codes
SUPPORTED_LANGUAGES = {
    "english": "en",
    "yoruba": "yo",
    "hausa": "ha",
    "igbo": "ig",
    "pidgin": "en",  # Whisper treats pidgin as English variant
    "french": "fr",  # For francophone West Africa
}

# Translation prompts for each language
TRANSLATION_PROMPTS = {
    "yoruba": "Translate this Yoruba text to English accurately, preserving agricultural context:",
    "hausa": "Translate this Hausa text to English accurately, preserving agricultural context:",
    "igbo": "Translate this Igbo text to English accurately, preserving agricultural context:",
    "pidgin": "Convert this Nigerian Pidgin English to standard English, preserving meaning:",
    "english": None,  # No translation needed
}

# Response language prompts
RESPONSE_LANGUAGE_PROMPTS = {
    "yoruba": "Translate your response to Yoruba language. Keep it natural and conversational for a Nigerian farmer:",
    "hausa": "Translate your response to Hausa language. Keep it natural and conversational for a Nigerian farmer:",
    "igbo": "Translate your response to Igbo language. Keep it natural and conversational for a Nigerian farmer:",
    "pidgin": "Rewrite your response in Nigerian Pidgin English. Keep it natural and conversational:",
    "english": None,  # No translation needed
}


async def transcribe_audio(
    audio_bytes: bytes,
    filename: str,
    language_hint: Optional[str] = None
) -> dict:
    """
    Transcribes audio using Groq's Whisper model.
    Supports English, Yoruba, Hausa, Igbo, and Nigerian Pidgin.
    """
    logger.info(f"Transcribing audio: {len(audio_bytes)} bytes, "
                f"filename={filename}, language_hint={language_hint}")

    try:
        # Determine Whisper language code
        whisper_lang = None
        if language_hint and language_hint in SUPPORTED_LANGUAGES:
            whisper_lang = SUPPORTED_LANGUAGES[language_hint]

        # Create file-like object for Groq API
        audio_file = (filename, io.BytesIO(audio_bytes), _get_audio_mime(filename))

        # Transcribe with Whisper
        transcription_params = {
            "file": audio_file,
            "model": "whisper-large-v3",
            "response_format": "verbose_json",  # gives us language detection too
            "temperature": 0.0
        }

        if whisper_lang:
            transcription_params["language"] = whisper_lang

        logger.info("Sending audio to Groq Whisper model...")
        response = client.audio.transcriptions.create(**transcription_params)

        transcribed_text = response.text.strip()
        detected_language = getattr(response, "language", language_hint or "english")

        logger.info(f"Transcription complete: '{transcribed_text[:80]}...' "
                   f"(detected_language: {detected_language})")

        return {
            "success": True,
            "transcribed_text": transcribed_text,
            "detected_language": detected_language,
            "duration_seconds": getattr(response, "duration", None)
        }

    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def translate_to_english(text: str, source_language: str) -> str:
    """
    Translates Nigerian language text to English for agent processing.
    Returns original text if already English.
    """
    if source_language.lower() in ("english", "en"):
        return text

    translation_prompt = TRANSLATION_PROMPTS.get(source_language.lower())
    if not translation_prompt:
        logger.warning(f"No translation prompt for language: {source_language}")
        return text

    logger.info(f"Translating from {source_language} to English...")

    system_prompt = f"""
    You are an expert translator specializing in Nigerian languages and agricultural terminology.
    {translation_prompt}
    
    Return ONLY the English translation. No explanations, no notes.
    """

    try:
        translated = await ask_llm(
            user_message=text,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=500
        )
        logger.info(f"Translation complete: '{translated[:80]}'")
        return translated
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        return text  # Fall back to original


async def translate_response_to_language(
    response_text: str,
    target_language: str
) -> str:
    """
    Translates agent response to farmer's preferred language.
    Returns original if target is English.
    """
    if target_language.lower() in ("english", "en"):
        return response_text

    language_prompt = RESPONSE_LANGUAGE_PROMPTS.get(target_language.lower())
    if not language_prompt:
        return response_text

    logger.info(f"Translating response to {target_language}...")

    system_prompt = f"""
    You are an expert translator for Nigerian languages specializing in 
    agricultural and farming terminology.
    {language_prompt}
    
    Keep the translation natural and easy to understand for a Nigerian farmer.
    Preserve all specific names (diseases, chemicals, crop varieties) in their 
    original form since farmers will recognize them better.
    Return ONLY the translated text.
    """

    try:
        translated = await ask_llm(
            user_message=response_text,
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=800
        )
        logger.info(f"Response translated to {target_language}")
        return translated
    except Exception as e:
        logger.error(f"Response translation failed: {e}")
        return response_text  # Fall back to English


async def process_voice_message(
    audio_bytes: bytes,
    filename: str,
    farmer_id: str,
    preferred_language: str = "english",
    crop_context: Optional[str] = None
) -> dict:
    """
    Full voice message pipeline:
    1. Transcribe audio → text
    2. Translate to English if needed
    3. Send to agent
    4. Translate response back to farmer's language
    """
    from app.agent.agent import run_agent

    # Step 1: Transcribe
    transcription = await transcribe_audio(
        audio_bytes=audio_bytes,
        filename=filename,
        language_hint=preferred_language
    )

    if not transcription["success"]:
        return {
            "success": False,
            "error": f"Could not transcribe audio: {transcription.get('error')}",
            "transcribed_text": None,
            "reply": None
        }

    transcribed_text = transcription["transcribed_text"]
    detected_language = transcription.get("detected_language", preferred_language)

    if not transcribed_text:
        return {
            "success": False,
            "error": "No speech detected in the audio. Please speak clearly and try again.",
            "transcribed_text": None,
            "reply": None
        }

    # Step 2: Translate to English for agent processing
    english_text = await translate_to_english(transcribed_text, detected_language)

    # Step 3: Run through agent
    logger.info(f"Processing voice message through agent: '{english_text[:80]}'")
    agent_result = await run_agent(
        user_message=english_text,
        farmer_id=farmer_id,
        crop_context=crop_context
    )

    agent_reply = agent_result.get("reply", "")
    tools_used = agent_result.get("tools_used", [])
    session_context = agent_result.get("session_context", {})

    # Step 4: Translate response to farmer's preferred language
    final_reply = await translate_response_to_language(
        response_text=agent_reply,
        target_language=preferred_language
    )

    return {
        "success": True,
        "transcribed_text": transcribed_text,
        "english_text": english_text,
        "detected_language": detected_language,
        "reply": final_reply,
        "tools_used": tools_used,
        "session_context": session_context
    }


def _get_audio_mime(filename: str) -> str:
    """Gets MIME type for audio file."""
    import os
    ext = os.path.splitext(filename.lower())[1]
    mime_types = {
        ".mp3": "audio/mpeg",
        ".mp4": "audio/mp4",
        ".wav": "audio/wav",
        ".m4a": "audio/m4a",
        ".ogg": "audio/ogg",
        ".webm": "audio/webm",
        ".flac": "audio/flac",
    }
    return mime_types.get(ext, "audio/mpeg")


def validate_audio(audio_bytes: bytes, filename: str) -> tuple[bool, str]:
    """Validates audio file before processing."""
    # Max 25MB (Whisper limit)
    max_size = 25 * 1024 * 1024
    if len(audio_bytes) > max_size:
        return False, "Audio file too large. Maximum size is 25MB."

    allowed_extensions = {".mp3", ".mp4", ".wav", ".m4a", ".ogg", ".webm", ".flac"}
    import os
    ext = os.path.splitext(filename.lower())[1]
    if ext not in allowed_extensions:
        return False, f"Unsupported audio format '{ext}'. Please use MP3, WAV, M4A, or WebM."

    if len(audio_bytes) < 1000:
        return False, "Audio file too small or empty. Please record again."

    return True, ""