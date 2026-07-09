from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from app.models.db.database import get_db
from app.services.auth_service import (
    create_user, authenticate_user, get_user_by_email,
    create_access_token, decode_token
)
from app.core.config import settings
from loguru import logger
import httpx

router = APIRouter()


# --- Schemas ---
class SignupRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    preferred_language: str = "english"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    success: bool
    access_token: str
    token_type: str = "bearer"
    farmer_id: str
    full_name: str
    email: str
    preferred_language: str
    message: str


class UserProfileResponse(BaseModel):
    farmer_id: str
    email: str
    full_name: str
    preferred_language: str
    auth_provider: str
    created_at: datetime


# --- Email Signup ---
@router.post("/signup", response_model=AuthResponse, tags=["Authentication"])
async def signup(request: SignupRequest, db: AsyncSession = Depends(get_db)):
    """Register a new farmer with email and password."""
    logger.info(f"Signup attempt: {request.email}")

    # Check if email already exists
    existing = await get_user_by_email(db, request.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists. Please login instead."
        )

    # Create user
    user = await create_user(
        db=db,
        email=request.email,
        full_name=request.full_name,
        password=request.password,
        preferred_language=request.preferred_language
    )

    # Generate token
    token = create_access_token({"sub": user.farmer_id, "email": user.email})

    return AuthResponse(
        success=True,
        access_token=token,
        farmer_id=user.farmer_id,
        full_name=user.full_name,
        email=user.email,
        preferred_language=user.preferred_language,
        message=f"Welcome to AgroTech, {user.full_name}! Your farmer ID is {user.farmer_id}"
    )


# --- Email Login ---
@router.post("/login", response_model=AuthResponse, tags=["Authentication"])
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with email and password."""
    logger.info(f"Login attempt: {request.email}")

    user = await authenticate_user(db, request.email, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Update last login
    user.last_login = datetime.utcnow()
    await db.commit()

    token = create_access_token({"sub": user.farmer_id, "email": user.email})

    return AuthResponse(
        success=True,
        access_token=token,
        farmer_id=user.farmer_id,
        full_name=user.full_name,
        email=user.email,
        preferred_language=user.preferred_language,
        message=f"Welcome back, {user.full_name}!"
    )


# --- Google OAuth ---
@router.get("/google", tags=["Authentication"])
async def google_login():
    """Redirects farmer to Google OAuth consent screen."""
    if not settings.google_client_id:
        raise HTTPException(status_code=503, detail="Google OAuth not configured")

    google_auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={settings.google_client_id}"
        f"&redirect_uri={settings.google_redirect_uri}"
        "&response_type=code"
        "&scope=openid email profile"
        "&access_type=offline"
    )
    return RedirectResponse(url=google_auth_url)


@router.get("/google/callback", tags=["Authentication"])
async def google_callback(code: str, db: AsyncSession = Depends(get_db)):
    """Handles Google OAuth callback — exchanges code for user info."""
    if not settings.google_client_id:
        raise HTTPException(status_code=503, detail="Google OAuth not configured")

    try:
        async with httpx.AsyncClient() as client:
            # Exchange code for tokens
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": settings.google_redirect_uri,
                    "grant_type": "authorization_code"
                }
            )
            token_data = token_response.json()

            # Get user info from Google
            user_info_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {token_data['access_token']}"}
            )
            google_user = user_info_response.json()

        email = google_user["email"]
        full_name = google_user.get("name", email.split("@")[0])
        google_id = google_user["id"]

        # Check if user exists
        existing = await get_user_by_email(db, email)

        if existing:
            # Update google_id if missing
            if not existing.google_id:
                existing.google_id = google_id
                await db.commit()
            user = existing
            msg = f"Welcome back, {user.full_name}!"
        else:
            # Create new user
            user = await create_user(
                db=db,
                email=email,
                full_name=full_name,
                auth_provider="google",
                google_id=google_id
            )
            msg = f"Welcome to AgroTech, {user.full_name}! Your farmer ID is {user.farmer_id}"

        # Update last login
        user.last_login = datetime.utcnow()
        await db.commit()

        token = create_access_token({"sub": user.farmer_id, "email": user.email})

        logger.info(f"Google OAuth success: {email} → {user.farmer_id}")

        # Return token info (in production, redirect to frontend with token)
        return {
            "success": True,
            "access_token": token,
            "token_type": "bearer",
            "farmer_id": user.farmer_id,
            "full_name": user.full_name,
            "email": user.email,
            "preferred_language": user.preferred_language,
            "message": msg
        }

    except Exception as e:
        logger.error(f"Google OAuth failed: {e}")
        raise HTTPException(status_code=500, detail=f"Google OAuth failed: {str(e)}")


# --- Get Current User (Protected Route) ---
async def get_current_user(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """Dependency: extracts and validates JWT token."""
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    farmer_id = payload.get("sub")
    from app.services.auth_service import get_user_by_farmer_id
    user = await get_user_by_farmer_id(db, farmer_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


@router.get("/me", response_model=UserProfileResponse, tags=["Authentication"])
async def get_profile(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """Get current farmer's profile using their JWT token."""
    user = await get_current_user(token, db)
    return UserProfileResponse(
        farmer_id=user.farmer_id,
        email=user.email,
        full_name=user.full_name,
        preferred_language=user.preferred_language,
        auth_provider=user.auth_provider,
        created_at=user.created_at
    )