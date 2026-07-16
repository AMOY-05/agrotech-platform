from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional


class Settings(BaseSettings):
    app_name: str = "AgroTech Intelligence Platform"
    app_version: str = "1.0.0"
    debug: bool = False
    groq_api_key: str
    openweather_api_key: str

    # Database
    database_url: str = "sqlite+aiosqlite:///./agrotech.db"

    # JWT
    secret_key: str = "your-super-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Google OAuth
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_redirect_uri: str = "https://agrotech-api-ooi0.onrender.com/api/v1/auth/google/callback"

    # Twilio WhatsApp
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_whatsapp_number: str = "whatsapp:+14155238886"
    
    #Whatapp bot
    meta_whatsapp_token: Optional[str] = None
    meta_phone_number_id: Optional[str] = None
    meta_verify_token: str = "agrotech_verify_2024"

    # Telegram Bot
    telegram_bot_token: Optional[str] = None
    
    streamlit_app_url: str = "https://agrotechintelligence.streamlit.app"

    # New AI providers
    anthropic_api_key: Optional[str] = None
    huggingface_token: Optional[str] = None

    model_config = {
        "env_file": Path(__file__).parent.parent.parent / ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }


settings = Settings()