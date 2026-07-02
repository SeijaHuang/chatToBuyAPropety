"""Unit tests for the anonymous user identity FastAPI dependencies."""

from unittest.mock import AsyncMock

import pytest

from exceptions import BadRequestError
from routers.deps import require_anon_id_cookie_async, resolve_anon_id_async

TEST_ANON_ID: str = "aaaabbbb-cccc-4000-aaaa-bbbbbbbbbbbb"


async def test_resolve_creates_new_user_when_no_cookie_async() -> None:
    """resolve_anon_id_async with no cookie delegates to get_or_create_async(None)."""
    mock_repo: AsyncMock = AsyncMock()
    mock_repo.get_or_create_async.return_value = TEST_ANON_ID

    result: str = await resolve_anon_id_async(propertyai_anon_id=None, anon_repo=mock_repo)

    mock_repo.get_or_create_async.assert_called_once_with(None)
    assert result == TEST_ANON_ID


async def test_resolve_returns_existing_user_when_cookie_valid_async() -> None:
    """resolve_anon_id_async with a valid UUID cookie passes it to get_or_create_async."""
    mock_repo: AsyncMock = AsyncMock()
    mock_repo.get_or_create_async.return_value = TEST_ANON_ID

    result: str = await resolve_anon_id_async(propertyai_anon_id=TEST_ANON_ID, anon_repo=mock_repo)

    mock_repo.get_or_create_async.assert_called_once_with(TEST_ANON_ID)
    assert result == TEST_ANON_ID


async def test_resolve_creates_new_user_when_cookie_malformed_async() -> None:
    """resolve_anon_id_async with a malformed cookie passes it to get_or_create_async."""
    mock_repo: AsyncMock = AsyncMock()
    mock_repo.get_or_create_async.return_value = TEST_ANON_ID

    result: str = await resolve_anon_id_async(propertyai_anon_id="not-a-uuid", anon_repo=mock_repo)

    mock_repo.get_or_create_async.assert_called_once_with("not-a-uuid")
    assert result == TEST_ANON_ID


async def test_require_raises_when_no_cookie_async() -> None:
    """require_anon_id_cookie_async raises BadRequestError when cookie is absent."""
    with pytest.raises(BadRequestError):
        await require_anon_id_cookie_async(propertyai_anon_id=None)


async def test_require_raises_when_cookie_not_uuid_async() -> None:
    """require_anon_id_cookie_async raises BadRequestError when cookie is not a UUID."""
    with pytest.raises(BadRequestError):
        await require_anon_id_cookie_async(propertyai_anon_id="not-a-uuid")


async def test_require_returns_valid_uuid_string_async() -> None:
    """require_anon_id_cookie_async returns the cookie value unchanged when it is a valid UUID."""
    result: str = await require_anon_id_cookie_async(propertyai_anon_id=TEST_ANON_ID)
    assert result == TEST_ANON_ID
