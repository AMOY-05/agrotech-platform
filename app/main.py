from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from loguru import logger
import time
from app.models.db.database import init_db

from app.core.config import settings
from app.api.routes import (
    health_routes,
    pest_routes,
    yield_routes,
    price_routes,
    agent_routes,
    weather_routes,
    auth_routes,
    image_routes,
    voice_routes,
    whatsapp_routes,
    telegram_routes,
    admin_routes
)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    description="AI-powered platform helping Nigerian farmers predict yields, detect pests, and time their market sales."
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logging Middleware
class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        duration = round(time.time() - start, 3)
        logger.info(f"{request.method} {request.url.path} → {response.status_code} ({duration}s)")
        return response

app.add_middleware(LoggingMiddleware)

# Routers
app.include_router(health_routes.router, prefix="/api/v1")
app.include_router(pest_routes.router, prefix="/api/v1/pest")
app.include_router(yield_routes.router, prefix="/api/v1/yield")
app.include_router(price_routes.router, prefix="/api/v1/price")
app.include_router(agent_routes.router, prefix="/api/v1/agent")
app.include_router(weather_routes.router, prefix="/api/v1/weather")
app.include_router(auth_routes.router, prefix="/api/v1/auth")
app.include_router(image_routes.router, prefix="/api/v1/image")
app.include_router(voice_routes.router, prefix="/api/v1/voice")
app.include_router(whatsapp_routes.router, prefix="/api/v1/whatsapp")
app.include_router(telegram_routes.router, prefix="/api/v1/telegram")
app.include_router(admin_routes.router, prefix="/api/v1/admin")

@app.on_event("startup")
async def startup_event():
    await init_db()
    logger.info("AgroTech Platform started successfully")

@app.get("/", tags=["System"])
async def root():
    return {
        "platform": settings.app_name,
        "version": settings.app_version,
        "status": "online",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}