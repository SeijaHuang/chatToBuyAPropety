"""Unit tests for the session_id FastAPI dependencies in routers/deps.py."""

import uuid

import pytest

from exceptions import BadRequestError
from models.requests.post_chat import ChatRequest
from routers.deps import require_valid_session_id_async, validate_optional_session_id_async

TEST_SESSION_ID: str = "11111111-1111-4111-a111-111111111111"


async def test_require_valid_session_id_returns_parsed_uuid_async() -> None:
    """require_valid_session_id_async returns the parsed UUID for a valid path segment."""
    result: uuid.UUID = await require_valid_session_id_async(session_id=TEST_SESSION_ID)
    assert result == uuid.UUID(TEST_SESSION_ID)


async def test_require_valid_session_id_raises_for_malformed_uuid_async() -> None:
    """require_valid_session_id_async raises BadRequestError for a non-UUID path segment."""
    with pytest.raises(BadRequestError):
        await require_valid_session_id_async(session_id="not-a-uuid")


async def test_validate_optional_session_id_returns_none_when_absent_async() -> None:
    """validate_optional_session_id_async returns None when the request omits session_id."""
    request = ChatRequest(session_id=None, message="Hi")
    result: uuid.UUID | None = await validate_optional_session_id_async(request)
    assert result is None


async def test_validate_optional_session_id_returns_parsed_uuid_async() -> None:
    """validate_optional_session_id_async returns the parsed UUID when session_id is valid."""
    request = ChatRequest(session_id=TEST_SESSION_ID, message="Hi")
    result: uuid.UUID | None = await validate_optional_session_id_async(request)
    assert result == uuid.UUID(TEST_SESSION_ID)


async def test_validate_optional_session_id_raises_for_malformed_uuid_async() -> None:
    """validate_optional_session_id_async raises BadRequestError for a malformed session_id."""
    request = ChatRequest(session_id="not-a-uuid", message="Hi")
    with pytest.raises(BadRequestError):
        await validate_optional_session_id_async(request)
