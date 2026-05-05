"""Shared pytest fixtures for the PropertyAI backend test suite."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from models.schemas import ConversationStateDTO


@pytest.fixture
async def client_async() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client wired to the FastAPI app under test."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_state() -> ConversationStateDTO:
    """Minimal valid ConversationStateDTO for use in unit tests."""
    return ConversationStateDTO(session_id="test-session-001")
