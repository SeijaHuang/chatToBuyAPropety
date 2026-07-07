"""Unit tests for the anonymous user identity FastAPI dependencies."""

import uuid
from unittest.mock import AsyncMock

import pytest

from exceptions import BadRequestError
from routers.deps import require_anon_id_cookie_async, resolve_anon_id_async

TEST_ANON_ID: str = "aaaabbbb-cccc-4000-aaaa-bbbbbbbbbbbb"


async def test_resolve_creates_new_user_when_no_cookie_async() -> None:
    """resolve_anon_id_async with no cookie delegates to get_or_create_async(None)."""
    mock_repo: AsyncMock = AsyncMock()
    mock_repo.get_or_create_async.return_value = uuid.UUID(TEST_ANON_ID)

    result: uuid.UUID = await resolve_anon_id_async(propertyai_anon_id=None, anon_repo=mock_repo)

    mock_repo.get_or_create_async.assert_called_once_with(None)
    assert result == uuid.UUID(TEST_ANON_ID)


async def test_resolve_returns_existing_user_when_cookie_valid_async() -> None:
    """resolve_anon_id_async parses a valid UUID cookie before calling get_or_create_async."""
    mock_repo: AsyncMock = AsyncMock()
    mock_repo.get_or_create_async.return_value = uuid.UUID(TEST_ANON_ID)

    result: uuid.UUID = await resolve_anon_id_async(
        propertyai_anon_id=TEST_ANON_ID, anon_repo=mock_repo
    )

    mock_repo.get_or_create_async.assert_called_once_with(uuid.UUID(TEST_ANON_ID))
    assert result == uuid.UUID(TEST_ANON_ID)


async def test_resolve_creates_new_user_when_cookie_malformed_async() -> None:
    """resolve_anon_id_async treats a malformed cookie as absent, passing None to the repo."""
    mock_repo: AsyncMock = AsyncMock()
    mock_repo.get_or_create_async.return_value = uuid.UUID(TEST_ANON_ID)

    result: uuid.UUID = await resolve_anon_id_async(
        propertyai_anon_id="not-a-uuid", anon_repo=mock_repo
    )

    mock_repo.get_or_create_async.assert_called_once_with(None)
    assert result == uuid.UUID(TEST_ANON_ID)


async def test_require_raises_when_no_cookie_async() -> None:
    """require_anon_id_cookie_async raises BadRequestError when cookie is absent."""
    with pytest.raises(BadRequestError):
        await require_anon_id_cookie_async(propertyai_anon_id=None)


async def test_require_raises_when_cookie_not_uuid_async() -> None:
    """require_anon_id_cookie_async raises BadRequestError when cookie is not a UUID."""
    with pytest.raises(BadRequestError):
        await require_anon_id_cookie_async(propertyai_anon_id="not-a-uuid")


async def test_require_returns_parsed_uuid_async() -> None:
    """require_anon_id_cookie_async returns the parsed UUID when the cookie is valid."""
    result: uuid.UUID = await require_anon_id_cookie_async(propertyai_anon_id=TEST_ANON_ID)
    assert result == uuid.UUID(TEST_ANON_ID)
