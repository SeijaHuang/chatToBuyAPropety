"""Repository for the users table — Protocol + SQLAlchemy implementation."""

import uuid
from typing import Protocol

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.connection import get_session_factory
from db.models.user import UserRow

logger: structlog.BoundLogger = structlog.get_logger()


class IUserRepository(Protocol):
    """Persistence contract for the users table."""

    async def get_or_create_async(self, anon_id: str | None) -> str:
        """Resolve or create a user identity by anon_id.

        When anon_id is None or not found in the database, inserts a new user
        row with a fresh UUID pair. When found, refreshes updated_at.

        Returns:
            The anon_id string for the resolved or newly created user.
        """
        ...


class SqlAlchemyUserRepository:
    """SQLAlchemy-backed implementation of IUserRepository."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_or_create_async(self, anon_id: str | None) -> str:
        """Resolve or create a user by anon_id, refreshing updated_at on hit.

        Args:
            anon_id: UUID string from the client (None on first request).

        Returns:
            The anon_id string of the resolved or newly created user.
        """
        if anon_id is not None:
            try:
                parsed: uuid.UUID = uuid.UUID(anon_id)
                found: str | None = await self._touch_existing_async(parsed)
                if found is not None:
                    return found
            except ValueError:
                # Malformed UUID from client — treat as absent, issue fresh identity
                logger.warning("anon_id_parse_failed", raw_anon_id=anon_id)

        return await self._create_new_async()

    async def _touch_existing_async(self, anon_uuid: uuid.UUID) -> str | None:
        """Update updated_at for an existing user row. Returns anon_id str or None."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(UserRow.anon_id).where(UserRow.anon_id == anon_uuid)
            )
            row_anon_id: uuid.UUID | None = result.scalar_one_or_none()
            if row_anon_id is None:
                return None
            await session.execute(
                update(UserRow).where(UserRow.anon_id == anon_uuid).values(updated_at=func.now())
            )
            await session.commit()
        return str(anon_uuid)

    async def _create_new_async(self) -> str:
        """Insert a new user row and return the generated anon_id string."""
        new_anon_id: uuid.UUID = uuid.uuid4()
        new_user_id: uuid.UUID = uuid.uuid4()
        async with self._session_factory() as session:
            await session.execute(
                pg_insert(UserRow).values(user_id=new_user_id, anon_id=new_anon_id)
            )
            await session.commit()
        logger.info("user_created", anon_id=str(new_anon_id))
        return str(new_anon_id)


def get_user_repository() -> SqlAlchemyUserRepository:
    """FastAPI dependency — returns a SqlAlchemyUserRepository."""
    return SqlAlchemyUserRepository(get_session_factory())
