"""
Redis-backed session store using Upstash.
Replaces in-memory dict with persistent Redis storage.
Falls back to in-memory if Redis unavailable.
"""
import json
import pickle
from datetime import datetime, timedelta
from typing import Optional
from loguru import logger
from app.core.config import settings

# Try to import Upstash Redis
try:
    from upstash_redis import Redis
    _redis_client = None

    def get_redis() -> Optional[Redis]:
        global _redis_client
        if _redis_client is not None:
            return _redis_client
        if not settings.redis_url or not settings.redis_token:
            return None
        try:
            _redis_client = Redis(
                url=settings.redis_url,
                token=settings.redis_token
            )
            # Test connection
            _redis_client.ping()
            logger.info("Redis connection established")
            return _redis_client
        except Exception as e:
            logger.warning(f"Redis connection failed: {e} — using in-memory fallback")
            return None

except ImportError:
    logger.warning("upstash-redis not installed — using in-memory sessions")
    def get_redis():
        return None


SESSION_TTL_SECONDS = 7200  # 2 hours
SESSION_PREFIX = "agrotech:session:"


class RedisSession:
    """
    Farmer session backed by Redis.
    Serializes to JSON for storage.
    """
    def __init__(self, farmer_id: str, data: dict = None):
        self.farmer_id = farmer_id
        self.created_at = datetime.utcnow().isoformat()
        self.last_active = datetime.utcnow().isoformat()
        self.messages = []
        self.context = {
            "crop_type": None,
            "region": None,
            "farm_size_hectares": None,
            "soil_type": None
        }

        # Restore from existing data if provided
        if data:
            self.created_at = data.get("created_at", self.created_at)
            self.last_active = data.get("last_active", self.last_active)
            self.messages = data.get("messages", [])
            self.context = data.get("context", self.context)

    def to_dict(self) -> dict:
        return {
            "farmer_id": self.farmer_id,
            "created_at": self.created_at,
            "last_active": datetime.utcnow().isoformat(),
            "messages": self.messages[-10:],  # Keep last 10
            "context": self.context
        }

    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        self.last_active = datetime.utcnow().isoformat()
        if len(self.messages) > 10:
            self.messages = self.messages[-10:]

    def update_context(self, **kwargs):
        for key, value in kwargs.items():
            if value is not None and key in self.context:
                self.context[key] = value
                logger.info(f"Session {self.farmer_id}: updated {key}={value}")

    def get_context_summary(self) -> str:
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
        try:
            last = datetime.fromisoformat(self.last_active)
            return datetime.utcnow() - last > timedelta(seconds=SESSION_TTL_SECONDS)
        except Exception:
            return False


def get_session_redis(farmer_id: str) -> RedisSession:
    """Gets session from Redis or creates new one."""
    redis = get_redis()
    key = f"{SESSION_PREFIX}{farmer_id}"

    if redis:
        try:
            data = redis.get(key)
            if data:
                session_data = json.loads(data)
                session = RedisSession(farmer_id, session_data)
                if session.is_expired():
                    logger.info(f"Session expired: {farmer_id}")
                    redis.delete(key)
                    return RedisSession(farmer_id)
                logger.info(f"Loaded session from Redis: {farmer_id}")
                return session
            else:
                logger.info(f"Creating new Redis session: {farmer_id}")
                return RedisSession(farmer_id)
        except Exception as e:
            logger.error(f"Redis get failed: {e} — using in-memory fallback")

    # Fallback to in-memory
    return _get_memory_session(farmer_id)


def save_session_redis(session: RedisSession):
    """Saves session to Redis."""
    redis = get_redis()
    key = f"{SESSION_PREFIX}{session.farmer_id}"

    if redis:
        try:
            data = json.dumps(session.to_dict())
            redis.setex(key, SESSION_TTL_SECONDS, data)
            logger.info(f"Saved session to Redis: {session.farmer_id}")
            return True
        except Exception as e:
            logger.error(f"Redis save failed: {e}")
            return False
    return False


def delete_session_redis(farmer_id: str):
    """Deletes a session from Redis."""
    redis = get_redis()
    if redis:
        try:
            redis.delete(f"{SESSION_PREFIX}{farmer_id}")
            logger.info(f"Deleted Redis session: {farmer_id}")
        except Exception as e:
            logger.error(f"Redis delete failed: {e}")


def get_active_session_count_redis() -> int:
    """Returns count of active sessions."""
    redis = get_redis()
    if redis:
        try:
            keys = redis.keys(f"{SESSION_PREFIX}*")
            return len(keys) if keys else 0
        except Exception:
            pass
    return len(_memory_sessions)


# ── In-memory fallback ──
_memory_sessions: dict = {}


def _get_memory_session(farmer_id: str) -> RedisSession:
    """In-memory session fallback when Redis unavailable."""
    if farmer_id in _memory_sessions:
        session = _memory_sessions[farmer_id]
        if session.is_expired():
            del _memory_sessions[farmer_id]
            return RedisSession(farmer_id)
        return session
    session = RedisSession(farmer_id)
    _memory_sessions[farmer_id] = session
    return session