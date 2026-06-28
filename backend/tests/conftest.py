"""Shared pytest fixtures for the PropertyAI backend test suite."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    create_async_engine,
)

from config import settings
from db.models import Base
from db.repositories.chat import SqlAlchemyChatRepository, get_chat_repository
from main import app
from models.conversation_state import ConversationStateDTO
from redis_store.client import redis_client


@pytest.fixture
async def client_async() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client wired to the FastAPI app under test.

    Redis, DB lifecycle, and the chat repository dependency are mocked so the
    test suite does not require live infrastructure. Individual tests that
    exercise those layers apply their own mocks via patch.
    """
    mock_repo: SqlAlchemyChatRepository = AsyncMock(spec=SqlAlchemyChatRepository)
    app.dependency_overrides[get_chat_repository] = lambda: mock_repo
    try:
        with (
            patch.object(redis_client, "connect_async", AsyncMock()),
            patch.object(redis_client, "close_async", AsyncMock()),
            patch("db.connection.create_engine_async", AsyncMock()),
            patch("db.connection.close_engine_async", AsyncMock()),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                yield ac
    finally:
        app.dependency_overrides.pop(get_chat_repository, None)


@pytest.fixture
def sample_state() -> ConversationStateDTO:
    """Minimal valid ConversationStateDTO for use in unit tests."""
    return ConversationStateDTO(session_id="test-session-001")


@pytest_asyncio.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Per-test async engine pointing at the real test database.

    Creates all tables idempotently on startup. Does not drop tables so
    subsequent tests inherit the schema without recreation overhead.
    Requires a live PostgreSQL instance (docker-compose postgres service).
    Skips automatically when PostgreSQL is unreachable.
    """
    import pytest
    from sqlalchemy.exc import OperationalError

    engine: AsyncEngine = create_async_engine(settings.database_url)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except (OperationalError, OSError, Exception) as exc:
        await engine.dispose()
        pytest.skip(
            f"PostgreSQL unavailable — start docker-compose postgres to run DB tests: {exc}"
        )
    yield engine
    await engine.dispose()
