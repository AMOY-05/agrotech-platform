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
# IMPORTANT: connect_args must only be set once, in exactly one branch.
engine_kwargs = {
    "echo": False,
    "future": True,
}

if "sqlite" in DATABASE_URL:
    # Local/dev SQLite
    engine_kwargs["connect_args"] = {"check_same_thread": False}

elif "pooler" in DATABASE_URL or ":6543" in DATABASE_URL:
    # Behind a pgbouncer-style external pooler (Supabase pooler, Neon -pooler).
    # The pooler does the pooling, so we must not pool again, and asyncpg's
    # prepared-statement cache breaks in transaction-pooling mode.
    engine_kwargs["poolclass"] = NullPool
    engine_kwargs["connect_args"] = {"statement_cache_size": 0}

else:
    # Direct Postgres connection (Render Postgres, Supabase :5432, etc).
    # Keep a real pool — this is what removes the per-request connection cost.
    engine_kwargs.update(
        {
            "pool_pre_ping": True,   # fixes "connection is closed" after idle
            "pool_recycle": 280,     # retire connections before the server drops them
            "pool_size": 5,
            "max_overflow": 10,
            "pool_timeout": 30,
        }
    )

logger.info(
    f"DB engine mode: "
    f"{'sqlite' if 'sqlite' in DATABASE_URL else engine_kwargs.get('poolclass', 'pooled')}"
)

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