from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.pool import NullPool
from app.models.db.user_model import Base
from app.core.config import settings
from loguru import logger

DATABASE_URL = settings.database_url

# Build engine kwargs based on database type.
# IMPORTANT: connect_args must be set in exactly one branch, never twice.
engine_kwargs = {
    "echo": False,
    "future": True,
}

if "sqlite" in DATABASE_URL:
    # Local/dev SQLite
    engine_kwargs["connect_args"] = {"check_same_thread": False}

elif "pooler" in DATABASE_URL or ":6543" in DATABASE_URL:
    # Behind a pgbouncer-style external pooler (Supabase pooler, Neon -pooler).
    # The pooler pools for us, and asyncpg's prepared-statement cache breaks
    # in transaction-pooling mode.
    engine_kwargs["poolclass"] = NullPool
    engine_kwargs["connect_args"] = {"statement_cache_size": 0}

else:
    # Direct Postgres connection (Render Postgres, Supabase :5432, etc).
    # A real pool is what removes the per-request connection cost, and
    # pool_pre_ping is what fixes "connection is closed" after idle periods.
    engine_kwargs.update(
        {
            "pool_pre_ping": True,
            "pool_recycle": 280,
            "pool_size": 5,
            "max_overflow": 10,
            "pool_timeout": 30,
        }
    )

logger.info(f"DB engine configured: {list(engine_kwargs.keys())}")

engine = create_async_engine(DATABASE_URL, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db():
    """Creates all tables on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized successfully")


async def get_db():
    """Dependency injection for database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()