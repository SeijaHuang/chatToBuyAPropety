"""ISessionStore Protocol and Redis-backed session persistence."""

from typing import Protocol

import structlog

from config import settings
from models.conversation_state import ConversationStateDTO
from redis_store.client import redis_client

logger = structlog.get_logger()

_SESSION_PREFIX: str = "session:"


class ISessionStore(Protocol):
    """Protocol contract for session state persistence."""

    async def load_session_async(self, session_id: str) -> ConversationStateDTO | None:
        """Load session state from the backing store.

        Args:
            session_id: UUID v4 session identifier.

        Returns:
            ConversationStateDTO if found and not expired, None otherwise.
        """
        ...

    async def save_session_async(self, state: ConversationStateDTO) -> None:
        """Persist session state and reset the TTL.

        Args:
            state: Full conversation state to store.
        """
        ...


class RedisSessionStore(ISessionStore):
    """ISessionStore backed by Redis with a sliding 7-day TTL."""

    async def load_session_async(self, session_id: str) -> ConversationStateDTO | None:
        """Return the stored ConversationStateDTO, or None when absent or expired.

        Args:
            session_id: UUID v4 session identifier.

        Returns:
            Deserialised ConversationStateDTO on hit, None on miss or Redis error.
        """
        raw: str | None = await redis_client.get_async(f"{_SESSION_PREFIX}{session_id}")
        if raw is None:
            return None
        state: ConversationStateDTO = ConversationStateDTO.model_validate_json(raw)
        logger.info("session_loaded", session_id=session_id)
        return state

    async def save_session_async(self, state: ConversationStateDTO) -> None:
        """Persist session state to Redis and reset the sliding 7-day TTL.

        Args:
            state: Full conversation state to serialise and store.
        """
        payload: str = state.model_dump_json(by_alias=False)
        await redis_client.setex_async(
            f"{_SESSION_PREFIX}{state.session_id}",
            settings.redis_session_ttl,
            payload,
        )
        logger.info("session_saved", session_id=state.session_id)


session_store: RedisSessionStore = RedisSessionStore()
