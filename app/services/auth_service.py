from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.db.user_model import User
from app.core.config import settings
from loguru import logger
import uuid

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(password: str) -> str:
    # bcrypt has a 72-byte limit — truncate safely
    return pwd_context.hash(password[:72])


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password[:72], hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_farmer_id(db: AsyncSession, farmer_id: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.farmer_id == farmer_id))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    email: str,
    full_name: str,
    password: Optional[str] = None,
    auth_provider: str = "email",
    google_id: Optional[str] = None,
    preferred_language: str = "english"
) -> User:
    farmer_id = f"farmer_{uuid.uuid4().hex[:8]}"

    user = User(
        farmer_id=farmer_id,
        email=email,
        full_name=full_name,
        hashed_password=hash_password(password) if password else None,
        auth_provider=auth_provider,
        google_id=google_id,
        preferred_language=preferred_language,
        is_verified=True if auth_provider == "google" else False
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info(f"New user created: {email} → {farmer_id}")
    return user


async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str
) -> Optional[User]:
    user = await get_user_by_email(db, email)
    if not user:
        return None
    if not user.hashed_password:
        return None  # OAuth user trying to use password login
    if not verify_password(password, user.hashed_password):
        return None
    return user