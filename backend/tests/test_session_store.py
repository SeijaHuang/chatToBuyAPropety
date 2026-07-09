"""Unit tests for RedisSessionStore load and save operations."""

from unittest.mock import AsyncMock, patch

from models.shared.conversation_state import ConversationStateDTO
from redis_store.client import redis_client
from redis_store.session_store import RedisSessionStore

_SESSION_ID: str = "test-session-001"


async def test_load_returns_none_when_redis_has_no_key() -> None:
    """load_session_async returns None when Redis returns no value for the session key."""
    store: RedisSessionStore = RedisSessionStore()
    with patch.object(redis_client, "get_async", AsyncMock(return_value=None)):
        result: ConversationStateDTO | None = await store.load_session_async(_SESSION_ID)
    assert result is None


async def test_load_returns_state_when_redis_has_key() -> None:
    """load_session_async deserialises and returns the stored ConversationStateDTO."""
    state: ConversationStateDTO = ConversationStateDTO(session_id=_SESSION_ID)
    serialized: str = state.model_dump_json(by_alias=False)
    store: RedisSessionStore = RedisSessionStore()
    with patch.object(redis_client, "get_async", AsyncMock(return_value=serialized)):
        result: ConversationStateDTO | None = await store.load_session_async(_SESSION_ID)
    assert result is not None
    assert result.session_id == _SESSION_ID


async def test_save_calls_setex_with_correct_session_key() -> None:
    """save_session_async calls redis_client.setex_async with the expected prefixed key."""
    state: ConversationStateDTO = ConversationStateDTO(session_id=_SESSION_ID)
    mock_setex: AsyncMock = AsyncMock()
    store: RedisSessionStore = RedisSessionStore()
    with patch.object(redis_client, "setex_async", mock_setex):
        await store.save_session_async(state)
    mock_setex.assert_called_once()
    key: str = mock_setex.call_args.args[0]
    assert key == f"session:{_SESSION_ID}"
