from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime, timezone
from app.models.db.database import get_db
from app.services.auth_service import (
    create_user, authenticate_user, get_user_by_email,
    create_access_token, decode_token, get_current_user,
    create_password_reset_token, consume_password_reset_token,
    set_user_password,
)
from app.services.email_service import (
    send_email, reset_email_html, google_account_html,
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


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def strong_enough(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class SimpleMessageResponse(BaseModel):
    success: bool
    message: str


# --- Email Signup ---
@router.post("/signup", response_model=AuthResponse, tags=["Authentication"])
async def signup(request: SignupRequest, db: AsyncSession = Depends(get_db)):
    """Register a new farmer with email and password."""
    logger.info(f"Signup attempt: {request.email}")

    existing = await get_user_by_email(db, request.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists. Please login instead."
        )

    user = await create_user(
        db=db,
        email=request.email,
        full_name=request.full_name,
        password=request.password,
        preferred_language=request.preferred_language
    )

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

    user.last_login = datetime.now(timezone.utc)
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


# --- Forgot Password ---
@router.post("/forgot-password", response_model=SimpleMessageResponse,
             tags=["Authentication"])
async def forgot_password(
    request: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Request a password reset link.

    Always returns the same response whether or not the account exists.
    Differentiating would let an attacker harvest your registered emails.
    """
    generic = SimpleMessageResponse(
        success=True,
        message=(
            "If an account exists for that email, we've sent a reset link. "
            "Check your inbox and spam folder."
        ),
    )

    user = await get_user_by_email(db, request.email)
    if not user:
        logger.info(f"Reset requested for unknown email: {request.email}")
        return generic

    # Google-only accounts have no password to reset.
    if not user.hashed_password and user.auth_provider == "google":
        await send_email(
            to=user.email,
            subject="AgroTech — Sign in with Google",
            html_body=google_account_html(user.full_name),
        )
        return generic

    raw_token = await create_password_reset_token(db, user)

    frontend = getattr(
        settings, "streamlit_app_url", "https://agrotechintelligence.site"
    ).rstrip("/")
    reset_url = f"{frontend}/?reset_token={raw_token}"

    await send_email(
        to=user.email,
        subject="Reset your AgroTech password",
        html_body=reset_email_html(user.full_name, reset_url),
    )

    return generic


# --- Reset Password ---
@router.post("/reset-password", response_model=SimpleMessageResponse,
             tags=["Authentication"])
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Complete a password reset using the emailed token."""
    farmer_id = await consume_password_reset_token(db, request.token)
    if not farmer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This reset link is invalid or has expired. Please request a new one.",
        )

    ok = await set_user_password(db, farmer_id, request.new_password)
    if not ok:
        raise HTTPException(status_code=404, detail="Account not found")

    return SimpleMessageResponse(
        success=True,
        message="Password updated. You can now log in with your new password.",
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
    """Handles Google OAuth — returns auto-redirect HTML page."""
    if not settings.google_client_id:
        raise HTTPException(status_code=503, detail="Google OAuth not configured")

    try:
        async with httpx.AsyncClient() as client:
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

            user_info_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {token_data['access_token']}"}
            )
            google_user = user_info_response.json()

        email = google_user["email"]
        full_name = google_user.get("name", email.split("@")[0])
        google_id = google_user["id"]

        existing = await get_user_by_email(db, email)
        if existing:
            if not existing.google_id:
                existing.google_id = google_id
                await db.commit()
            user = existing
        else:
            user = await create_user(
                db=db,
                email=email,
                full_name=full_name,
                auth_provider="google",
                google_id=google_id
            )

        user.last_login = datetime.now(timezone.utc)
        await db.commit()

        token = create_access_token({"sub": user.farmer_id, "email": user.email})
        streamlit_url = getattr(
            settings, "streamlit_app_url", "https://agrotechintelligence.site"
        ).rstrip("/")

        logger.info(f"Google OAuth success: {email} → {user.farmer_id}")

        html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>AgroTech — Logging you in...</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                        background: linear-gradient(135deg, #2d5a27, #4a9e3f);
                        color: white;
                        text-align: center;
                    }}
                    .container {{
                        padding: 40px;
                        border-radius: 15px;
                        background: rgba(255,255,255,0.1);
                    }}
                    .spinner {{
                        width: 50px;
                        height: 50px;
                        border: 5px solid rgba(255,255,255,0.3);
                        border-top: 5px solid white;
                        border-radius: 50%;
                        animation: spin 1s linear infinite;
                        margin: 20px auto;
                    }}
                    @keyframes spin {{
                        0% {{ transform: rotate(0deg); }}
                        100% {{ transform: rotate(360deg); }}
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🌾 AgroTech</h1>
                    <div class="spinner"></div>
                    <p>Welcome, {full_name}! Logging you in...</p>
                    <p id="status">Redirecting to your dashboard...</p>
                </div>
                <script>
                    sessionStorage.setItem('agrotech_token', '{token}');
                    sessionStorage.setItem('agrotech_farmer_id', '{user.farmer_id}');
                    sessionStorage.setItem('agrotech_name', '{full_name}');
                    sessionStorage.setItem('agrotech_language', '{user.preferred_language}');

                    setTimeout(function() {{
                        window.location.href = '{streamlit_url}?token={token}&farmer_id={user.farmer_id}&name={full_name}&language={user.preferred_language}';
                    }}, 1500);
                </script>
            </body>
            </html>
            """
        return HTMLResponse(content=html_content)

    except Exception as e:
        logger.error(f"Google OAuth failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Google OAuth failed: {str(e)}"
        )


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