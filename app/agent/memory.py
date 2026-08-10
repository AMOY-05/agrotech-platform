"""
Session memory — uses Redis when available, falls back to in-memory.
"""
from app.agent.redis_memory import (
    RedisSession,
    get_session_redis,
    save_session_redis,
    get_active_session_count_redis
)
from loguru import logger
from typing import Optional

# Re-export RedisSession as FarmerSession for backward compatibility
FarmerSession = RedisSession


def get_session(farmer_id: str) -> FarmerSession:
    """Gets or creates a farmer session."""
    if not farmer_id or farmer_id == "anonymous":
        farmer_id = "anonymous"
    return get_session_redis(farmer_id)


def get_active_session_count() -> int:
    """Returns number of active sessions."""
    return get_active_session_count_redis()


async def extract_and_update_context(session: FarmerSession, user_message: str):
    """
    Extracts farmer context from message and updates session.
    Saves to Redis after update.
    """
    from app.services.llm_service import ask_llm_structured
    import json
    import re

    EXTRACT_PROMPT = """
    Extract farmer context from this message. Return ONLY a JSON object.
    If a field is not mentioned, use null.

    {
        "crop_type": "crop name or null",
        "region": "Nigerian state/city or null",
        "farm_size_hectares": number or null,
        "soil_type": "loamy/sandy/clay/silty or null"
    }

    Return ONLY the JSON. No greeting, no explanation, no extra text.
    """

    try:
        raw = await ask_llm_structured(
            user_message, EXTRACT_PROMPT, temperature=0.1
        )
        cleaned = re.sub(r"```json|```", "", raw).strip()
        if not cleaned.startswith("{"):
            return
        extracted = json.loads(cleaned)
        session.update_context(**extracted)

        # Save updated session to Redis
        save_session_redis(session)

    except Exception as e:
        logger.warning(f"Context extraction failed (non-critical): {e}")