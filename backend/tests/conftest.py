"""Shared pytest fixtures for the PropertyAI backend test suite."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.fixture
async def client_async() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client wired to the FastAPI app under test."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_state() -> dict[str, object]:
    """Minimal valid ConversationStateDTO-shaped dict for use in unit tests."""
    return {
        "session_id": "test-session-001",
        "current_module": "M1_PROPERTY_NEEDS",
        "status": "IN_PROGRESS",
        "collected_data": {
            "property_type": None,
            "bedrooms": None,
            "bathrooms": None,
            "budget_min": None,
            "budget_max": None,
            "preferred_suburbs": [],
        },
        "messages": [],
    }
