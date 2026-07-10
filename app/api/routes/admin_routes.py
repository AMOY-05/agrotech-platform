from fastapi import APIRouter, HTTPException
from sqlalchemy import select, func
from app.models.db.database import get_db
from app.models.db.user_model import User
from app.agent.memory import get_active_session_count
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, date
from loguru import logger

router = APIRouter()


@router.get("/stats", tags=["Admin"])
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Returns platform statistics for admin dashboard."""
    try:
        # Total users
        total_users_result = await db.execute(
            select(func.count(User.id))
        )
        total_users = total_users_result.scalar() or 0

        # New users today
        today = datetime.combine(date.today(), datetime.min.time())
        new_today_result = await db.execute(
            select(func.count(User.id)).where(User.created_at >= today)
        )
        new_users_today = new_today_result.scalar() or 0

        # Google vs email users
        google_result = await db.execute(
            select(func.count(User.id)).where(
                User.auth_provider == "google"
            )
        )
        google_users = google_result.scalar() or 0

        # Telegram users (farmer_id starts with farmer_tg_)
        telegram_result = await db.execute(
            select(func.count(User.id)).where(
                User.farmer_id.like("farmer_tg_%")
            )
        )
        telegram_users = telegram_result.scalar() or 0

        # Active sessions
        active_sessions = get_active_session_count()

        return {
            "total_users": total_users,
            "new_users_today": new_users_today,
            "google_users": google_users,
            "telegram_users": telegram_users,
            "active_sessions": active_sessions,
            "total_messages": active_sessions * 5,  # estimate
            "messages_today": new_users_today * 3,  # estimate
            "total_agent_calls": total_users * 8,   # estimate
        }

    except Exception as e:
        logger.error(f"Stats fetch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users", tags=["Admin"])
async def get_users(
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Returns list of recent users for admin dashboard."""
    try:
        result = await db.execute(
            select(User).order_by(User.created_at.desc()).limit(limit)
        )
        users = result.scalars().all()

        return {
            "users": [
                {
                    "farmer_id": u.farmer_id,
                    "email": u.email,
                    "full_name": u.full_name,
                    "auth_provider": u.auth_provider,
                    "preferred_language": u.preferred_language,
                    "is_active": u.is_active,
                    "created_at": str(u.created_at),
                    "last_login": str(u.last_login) if u.last_login else None
                }
                for u in users
            ],
            "total": len(users)
        }

    except Exception as e:
        logger.error(f"Users fetch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))