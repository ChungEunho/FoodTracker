"""
SQLAlchemy async engine and session factory for NutriTrack.

Usage in FastAPI route dependencies:

    from app.db.session import get_db
    from sqlalchemy.ext.asyncio import AsyncSession

    @router.get("/meals")
    async def list_meals(db: AsyncSession = Depends(get_db)):
        ...

The engine is module-level and shared across all requests.
asyncpg handles its own connection pool internally.
"""

import ssl as ssl_lib
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings


def _make_ssl_context(database_url: str) -> ssl_lib.SSLContext | None:
    """
    Return an SSLContext for external DB connections, or None for local/internal connections.

    asyncpg passes this directly to the underlying TLS handshake.
    Internal Railway hosts (.railway.internal) and localhost skip SSL — they run on
    private networks where certificate verification is unavailable or unnecessary.
    """
    if (
        "localhost" in database_url
        or "127.0.0.1" in database_url
        or "railway.internal" in database_url
    ):
        return None
    ctx = ssl_lib.create_default_context()
    return ctx


# Create the async engine once at import time.
# echo=False in production; set echo=True locally to log SQL for debugging.
engine = create_async_engine(
    settings.database_url,
    connect_args={"ssl": _make_ssl_context(settings.database_url)},
    echo=False,
    # Pool sizing — tune per deployment.
    # Supabase free tier allows ~15 direct connections; leave headroom for migrations.
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # verify connections before use; handles idle-timeout disconnects
)

# Session factory.
# expire_on_commit=False keeps loaded attributes accessible after commit in async code.
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an AsyncSession and ensures it is closed
    after the request, even if an exception is raised.

    Rolls back automatically on exception (context manager semantics of AsyncSession).
    """
    async with AsyncSessionLocal() as session:
        yield session
