"""AsyncEngine and session factory lifecycle management."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def create_engine_async() -> None:
    """Initialise the async engine and session factory.

    Called once during FastAPI lifespan startup.
    """
    global _engine, _session_factory
    _engine = create_async_engine(
        settings.database_url,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        echo=False,
    )
    _session_factory = async_sessionmaker(
        bind=_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )


async def close_engine_async() -> None:
    """Dispose the engine. Called during FastAPI lifespan shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the active session factory.

    Raises:
        RuntimeError: If called before create_engine_async() has completed.
    """
    if _session_factory is None:
        raise RuntimeError("DB engine not initialised — call create_engine_async() first.")
    return _session_factory


async def get_db_session_async() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency — yields a managed AsyncSession per request.

    Usage:
        session: AsyncSession = Depends(get_db_session_async)
    """
    factory: async_sessionmaker[AsyncSession] = get_session_factory()
    async with factory() as session:
        yield session
