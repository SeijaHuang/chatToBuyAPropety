"""Repository for the chats table — Protocol + SQLAlchemy implementation."""

import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Protocol, TypedDict, cast

import structlog
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.connection import get_session_factory
from db.orm.chat import ChatRow
from models.chat import ChatSessionDTO
from models.conversation_state import CollectedData, ConversationStateDTO, EStatus, EUserIntent
from models.financial import BorrowingCapacityResult

logger: structlog.BoundLogger = structlog.get_logger()


class _BorrowingCapacityFields(TypedDict):
    """Mirrors BorrowingCapacityResult fields — used to cast JSONB dict before unpacking."""

    estimated_capacity: int
    monthly_repayment: int
    based_on_salary: int
    is_joint: bool
    annual_rate: float
    loan_term_years: int
    rate_source: str
    disclaimer: str


class IChatRepository(Protocol):
    """Persistence contract for the chats table."""

    async def upsert_chat_snapshot_async(
        self, state: ConversationStateDTO, anon_id: uuid.UUID
    ) -> None:
        """Write or update the chats row for the given session.

        Called after each module completes. Idempotent — repeated calls with
        the same state produce the same row, not duplicate rows.
        Exceptions must be logged and suppressed; must never propagate to the caller.
        """
        ...

    async def list_chats_by_anon_async(self, anon_id: uuid.UUID) -> list[ChatSessionDTO]:
        """Return all session records for an anonymous user, newest first.

        Returns an empty list when the anon_id has no persisted chats.
        """
        ...

    async def get_chat_snapshot_async(self, session_id: uuid.UUID) -> ConversationStateDTO | None:
        """Return a partially-constructed ConversationStateDTO from the DB row, or None.

        Used by the session-restore path when Redis misses. Returns None when
        the session is not found.

        Note: completion_status and current_module are left at defaults.
        Caller must call recalculate_completion() before using the returned state.
        """
        ...


class SqlAlchemyChatRepository(IChatRepository):
    """SQLAlchemy-backed implementation of IChatRepository.

    Uses PostgreSQL's INSERT ... ON CONFLICT DO UPDATE for atomic upserts.
    COALESCE guards ensure initial_intent and completed_at are never
    overwritten by NULL once written.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def upsert_chat_snapshot_async(
        self, state: ConversationStateDTO, anon_id: uuid.UUID
    ) -> None:
        """Upsert the chats row. Exceptions are logged and suppressed."""
        try:
            await self._do_upsert_async(state, anon_id)
        except Exception:
            logger.exception("db_upsert_failed", session_id=state.session_id)

    async def list_chats_by_anon_async(self, anon_id: uuid.UUID) -> list[ChatSessionDTO]:
        """Return session records for an anon user, ordered newest first."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(ChatRow)
                .where(ChatRow.anon_id == anon_id)
                .order_by(ChatRow.updated_at.desc())
            )
            rows: list[ChatRow] = list(result.scalars().all())

        return [
            ChatSessionDTO(
                session_id=str(row.session_id),
                status=row.status,
                initial_intent=row.initial_intent,
                created_at=row.created_at,
                updated_at=row.updated_at,
                completed_at=row.completed_at,
            )
            for row in rows
        ]

    async def get_chat_snapshot_async(self, session_id: uuid.UUID) -> ConversationStateDTO | None:
        """Return a partially-constructed ConversationStateDTO from the DB, or None.

        Deserialises collected_data and borrowing_capacity from JSONB into domain
        objects. completion_status and current_module are left at defaults — caller
        must call recalculate_completion() before using the returned state.
        """
        async with self._session_factory() as session:
            result = await session.execute(select(ChatRow).where(ChatRow.session_id == session_id))
            row: ChatRow | None = result.scalar_one_or_none()

        if row is None:
            return None

        collected_data: CollectedData = CollectedData.model_validate(row.collected_data)
        borrowing_capacity: BorrowingCapacityResult | None = (
            BorrowingCapacityResult(**cast(_BorrowingCapacityFields, row.borrowing_capacity))
            if row.borrowing_capacity is not None
            else None
        )
        return ConversationStateDTO(
            session_id=str(row.session_id),
            status=EStatus(row.status),
            initial_intent=EUserIntent(row.initial_intent)
            if row.initial_intent is not None
            else None,
            collected_data=collected_data,
            borrowing_capacity=borrowing_capacity,
        )

    async def _do_upsert_async(self, state: ConversationStateDTO, anon_id: uuid.UUID) -> None:
        """Execute the PostgreSQL upsert statement."""
        collected: dict[str, object] = state.collected_data.model_dump(by_alias=False)
        final_needs: dict[str, object] | None = (
            state.final_needs.model_dump(by_alias=False) if state.final_needs is not None else None
        )
        borrowing: dict[str, object] | None = (
            asdict(state.borrowing_capacity) if state.borrowing_capacity is not None else None
        )
        completed_at: datetime | None = (
            datetime.now(tz=UTC) if state.status == EStatus.REQUIREMENTS_COMPLETE else None
        )
        initial_intent: str | None = (
            state.initial_intent.value if state.initial_intent is not None else None
        )

        stmt = (
            pg_insert(ChatRow)
            .values(
                session_id=uuid.UUID(state.session_id),
                anon_id=anon_id,
                status=state.status.value,
                schema_version="1.1",
                initial_intent=initial_intent,
                collected_data=collected,
                final_needs=final_needs,
                borrowing_capacity=borrowing,
                completed_at=completed_at,
            )
            .on_conflict_do_update(
                index_elements=["session_id"],
                set_={
                    "status": pg_insert(ChatRow).excluded.status,
                    # COALESCE: once written, initial_intent is never overwritten by NULL
                    "initial_intent": func.coalesce(
                        pg_insert(ChatRow).excluded.initial_intent,
                        ChatRow.initial_intent,
                    ),
                    "collected_data": pg_insert(ChatRow).excluded.collected_data,
                    "final_needs": pg_insert(ChatRow).excluded.final_needs,
                    "borrowing_capacity": pg_insert(ChatRow).excluded.borrowing_capacity,
                    "updated_at": datetime.now(tz=UTC),
                    # COALESCE: once written, completed_at is never overwritten by NULL
                    "completed_at": func.coalesce(
                        pg_insert(ChatRow).excluded.completed_at,
                        ChatRow.completed_at,
                    ),
                    # anon_id is intentionally absent — session ownership is immutable
                },
            )
        )

        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()


def get_chat_repository() -> IChatRepository:
    """FastAPI dependency — returns a SqlAlchemyChatRepository."""
    return SqlAlchemyChatRepository(get_session_factory())
