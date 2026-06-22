"""Shared pytest fixtures for the PropertyAI backend test suite."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from models.conversation_state import ConversationStateDTO
from redis_store.client import redis_client


@pytest.fixture
async def client_async() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client wired to the FastAPI app under test.

    Redis connect/close are mocked so the test suite does not require a live
    Redis instance. Individual tests that exercise Redis behaviour apply their
    own session_store mocks via _mock_session().
    """
    with (
        patch.object(redis_client, "connect_async", AsyncMock()),
        patch.object(redis_client, "close_async", AsyncMock()),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


@pytest.fixture
def sample_state() -> ConversationStateDTO:
    """Minimal valid ConversationStateDTO for use in unit tests."""
    return ConversationStateDTO(session_id="test-session-001")
