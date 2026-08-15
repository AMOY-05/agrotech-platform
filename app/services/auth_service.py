from datetime import datetime, timedelta, timezone
from typing import Optional
import anyio
import uuid

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db.user_model import User
from app.core.config import settings
from loguru import logger

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


# ---------------------------------------------------------------------------
# Password hashing
#
# bcrypt is CPU-bound and deliberately slow (~250-500ms at 12 rounds on
# Render's 0.5 CPU). Calling it directly inside an `async def` blocks the
# entire event loop, so concurrent logins queue behind each other instead of
# running in parallel. anyio.to_thread.run_sync moves it to a worker thread.
# ---------------------------------------------------------------------------

def hash_password_sync(password: str) -> str:
    # bcrypt has a 72-byte limit — truncate safely
    return pwd_context.hash(password[:72])


def verify_password_sync(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password[:72], hashed_password)


async def hash_password(password: str) -> str:
    return await anyio.to_thread.run_sync(hash_password_sync, password)


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    return await anyio.to_thread.run_sync(
        verify_password_sync, plain_password, hashed_password
    )


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_farmer_id(db: AsyncSession, farmer_id: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.farmer_id == farmer_id))
    return result.scalar_one_or_none()


async def get_current_user(token: str, db: AsyncSession) -> User:
    """Resolve a JWT into a User. Raises 401 if invalid."""
    from fastapi import HTTPException, status

    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    farmer_id = payload.get("sub")
    if not farmer_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user = await get_user_by_farmer_id(db, farmer_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------

async def create_user(
    db: AsyncSession,
    email: str,
    full_name: str,
    password: Optional[str] = None,
    auth_provider: str = "email",
    google_id: Optional[str] = None,
    preferred_language: str = "english",
) -> User:
    farmer_id = f"farmer_{uuid.uuid4().hex[:8]}"

    hashed = await hash_password(password) if password else None

    user = User(
        farmer_id=farmer_id,
        email=email,
        full_name=full_name,
        hashed_password=hashed,
        auth_provider=auth_provider,
        google_id=google_id,
        preferred_language=preferred_language,
        is_verified=True if auth_provider == "google" else False,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info(f"New user created: {email} → {farmer_id}")
    return user


async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> Optional[User]:
    user = await get_user_by_email(db, email)
    if not user:
        return None
    if not user.hashed_password:
        return None  # OAuth user trying to use password login
    if not await verify_password(password, user.hashed_password):
        return None
    return user