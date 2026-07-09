from datetime import datetime, timedelta
from typing import Optional
from loguru import logger

# In-memory session store — keyed by farmer_id
# Each session holds conversation history + extracted farmer context
_sessions: dict = {}

# Sessions expire after 2 hours of inactivity
SESSION_TTL_HOURS = 2


class FarmerSession:
    def __init__(self, farmer_id: str):
        self.farmer_id = farmer_id
        self.created_at = datetime.utcnow()
        self.last_active = datetime.utcnow()
        self.messages = []  # full conversation history for LLM context
        self.context = {    # extracted farmer profile within this session
            "crop_type": None,
            "region": None,
            "farm_size_hectares": None,
            "soil_type": None,
        }

    def add_message(self, role: str, content: str):
        """Adds a message to conversation history."""
        self.messages.append({"role": role, "content": content})
        self.last_active = datetime.utcnow()
        # Keep last 10 messages to avoid hitting token limits
        if len(self.messages) > 10:
            self.messages = self.messages[-10:]

    def update_context(self, **kwargs):
        """Updates known farmer context — only overwrites if new value is provided."""
        for key, value in kwargs.items():
            if value is not None and key in self.context:
                self.context[key] = value
                logger.info(f"Session {self.farmer_id}: updated {key}={value}")

    def get_context_summary(self) -> str:
        """Returns a human-readable context string to inject into the system prompt."""
        filled = {k: v for k, v in self.context.items() if v is not None}
        if not filled:
            return ""
        parts = []
        if filled.get("crop_type"):
            parts.append(f"crop: {filled['crop_type']}")
        if filled.get("region"):
            parts.append(f"region: {filled['region']}")
        if filled.get("farm_size_hectares"):
            parts.append(f"farm size: {filled['farm_size_hectares']} hectares")
        if filled.get("soil_type"):
            parts.append(f"soil type: {filled['soil_type']}")
        return "Known farmer context: " + ", ".join(parts)

    def is_expired(self) -> bool:
        return datetime.utcnow() - self.last_active > timedelta(hours=SESSION_TTL_HOURS)


def get_session(farmer_id: str) -> FarmerSession:
    """Gets existing session or creates a new one."""
    _cleanup_expired_sessions()

    if farmer_id not in _sessions:
        logger.info(f"Creating new session for farmer: {farmer_id}")
        _sessions[farmer_id] = FarmerSession(farmer_id)
    else:
        session = _sessions[farmer_id]
        if session.is_expired():
            logger.info(f"Session expired for farmer: {farmer_id}, creating fresh session")
            _sessions[farmer_id] = FarmerSession(farmer_id)

    return _sessions[farmer_id]


def _cleanup_expired_sessions():
    """Removes expired sessions to prevent memory leak."""
    expired = [fid for fid, s in _sessions.items() if s.is_expired()]
    for fid in expired:
        del _sessions[fid]
        logger.info(f"Cleaned up expired session: {fid}")


def get_active_session_count() -> int:
    """Useful for monitoring."""
    return len([s for s in _sessions.values() if not s.is_expired()])

async def extract_and_update_context(session: FarmerSession, user_message: str):
    """
    Uses LLM to extract farmer context clues from the message.
    Runs silently — never affects the main conversation.
    """
    from app.services.llm_service import ask_llm_structured
    import json
    import re

    EXTRACT_PROMPT = """
    Extract farmer context from this message. Return ONLY a JSON object.
    If a field is not mentioned, use null.
    Do NOT include this JSON in any conversational response.
    This is a silent background extraction only.

    {
        "crop_type": "crop name or null",
        "region": "Nigerian state/city or null",
        "farm_size_hectares": number or null,
        "soil_type": "loamy/sandy/clay/silty or null"
    }

    Return ONLY the JSON. No greeting, no explanation, no extra text.
    """

    try:
        raw = await ask_llm_structured(user_message, EXTRACT_PROMPT, temperature=0.1)
        cleaned = re.sub(r"```json|```", "", raw).strip()

        # Extra safety: only parse if it looks like JSON
        if not cleaned.startswith("{"):
            return

        extracted = json.loads(cleaned)
        session.update_context(**extracted)
    except Exception as e:
        logger.warning(f"Context extraction failed (non-critical): {e}")