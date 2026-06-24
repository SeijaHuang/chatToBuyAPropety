"""Tests for SqlAlchemyChatRepository — uses a real PostgreSQL database."""

import uuid

import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from db.models.chat import ChatRow
from db.repositories.chat import SqlAlchemyChatRepository
from models.conversation_state import (
    ConversationStateDTO,
    EIntendedUse,
    EPropertyType,
    EStatus,
    EUserIntent,
)


def _make_repo(engine: AsyncEngine) -> SqlAlchemyChatRepository:
    """Build a repository backed by the test engine."""
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(engine, expire_on_commit=False)
    return SqlAlchemyChatRepository(factory)


def _fresh_state(session_id: str | None = None) -> ConversationStateDTO:
    sid: str = session_id or str(uuid.uuid4())
    return ConversationStateDTO(session_id=sid)


async def _fetch_row(engine: AsyncEngine, session_id: str) -> ChatRow | None:
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        result = await session.execute(
            select(ChatRow).where(ChatRow.session_id == uuid.UUID(session_id))
        )
        return result.scalar_one_or_none()


@pytest_asyncio.fixture(autouse=True)
async def _truncate_chats(db_engine: AsyncEngine) -> None:
    """Wipe the chats table before each test to ensure isolation."""
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        db_engine, expire_on_commit=False
    )
    async with factory() as session:
        await session.execute(delete(ChatRow))
        await session.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestChatRepository:
    """SqlAlchemyChatRepository"""

    async def test_upsert_creates_row_on_first_call(self, db_engine: AsyncEngine) -> None:
        state: ConversationStateDTO = _fresh_state()
        repo: SqlAlchemyChatRepository = _make_repo(db_engine)

        await repo.upsert_chat_snapshot_async(state)

        row: ChatRow | None = await _fetch_row(db_engine, state.session_id)
        assert row is not None
        assert str(row.session_id) == state.session_id
        assert row.status == EStatus.IN_PROGRESS

    async def test_upsert_on_m1_completion_writes_initial_intent(
        self, db_engine: AsyncEngine
    ) -> None:
        state: ConversationStateDTO = _fresh_state()
        state.completion_status.M1 = True
        state.initial_intent = EUserIntent.RECOMMEND_SUBURBS
        state.collected_data.m1.property_type = EPropertyType.HOUSE
        state.collected_data.m1.min_bedrooms = 3
        state.collected_data.m1.intended_use = EIntendedUse.OWNER_OCCUPIER
        repo: SqlAlchemyChatRepository = _make_repo(db_engine)

        await repo.upsert_chat_snapshot_async(state)

        row: ChatRow | None = await _fetch_row(db_engine, state.session_id)
        assert row is not None
        assert row.initial_intent == EUserIntent.RECOMMEND_SUBURBS.value

    async def test_upsert_on_m2_completion_accumulates_m1_data(
        self, db_engine: AsyncEngine
    ) -> None:
        state: ConversationStateDTO = _fresh_state()
        state.completion_status.M1 = True
        state.collected_data.m1.property_type = EPropertyType.UNIT
        repo: SqlAlchemyChatRepository = _make_repo(db_engine)

        # First upsert — M1 complete
        await repo.upsert_chat_snapshot_async(state)

        # Second upsert — M2 complete, m1 data still present
        state.completion_status.M2 = True
        state.collected_data.m2.household_size = 2
        await repo.upsert_chat_snapshot_async(state)

        row: ChatRow | None = await _fetch_row(db_engine, state.session_id)
        assert row is not None
        m1_data = row.collected_data["m1"]
        m2_data = row.collected_data["m2"]
        assert isinstance(m1_data, dict) and m1_data["property_type"] == EPropertyType.UNIT.value
        assert isinstance(m2_data, dict) and m2_data["household_size"] == 2

    async def test_upsert_on_m4_completion_writes_status_and_completed_at(
        self, db_engine: AsyncEngine
    ) -> None:
        state: ConversationStateDTO = _fresh_state()
        state.status = EStatus.REQUIREMENTS_COMPLETE
        state.completion_status.M1 = True
        state.completion_status.M2 = True
        state.completion_status.M3 = True
        state.completion_status.M4 = True
        state.collected_data.m4.budget_max = 800_000
        repo: SqlAlchemyChatRepository = _make_repo(db_engine)

        await repo.upsert_chat_snapshot_async(state)

        row: ChatRow | None = await _fetch_row(db_engine, state.session_id)
        assert row is not None
        assert row.status == EStatus.REQUIREMENTS_COMPLETE
        assert row.completed_at is not None

    async def test_upsert_is_idempotent_for_same_session_id(self, db_engine: AsyncEngine) -> None:
        state: ConversationStateDTO = _fresh_state()
        repo: SqlAlchemyChatRepository = _make_repo(db_engine)

        await repo.upsert_chat_snapshot_async(state)
        await repo.upsert_chat_snapshot_async(state)

        factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            db_engine, expire_on_commit=False
        )
        async with factory() as session:
            result = await session.execute(
                select(ChatRow).where(ChatRow.session_id == uuid.UUID(state.session_id))
            )
            rows = result.scalars().all()
        assert len(rows) == 1

    async def test_initial_intent_not_overwritten_by_subsequent_upsert(
        self, db_engine: AsyncEngine
    ) -> None:
        state: ConversationStateDTO = _fresh_state()
        state.initial_intent = EUserIntent.RECOMMEND_SUBURBS
        repo: SqlAlchemyChatRepository = _make_repo(db_engine)

        await repo.upsert_chat_snapshot_async(state)

        # Second upsert with no intent — COALESCE must preserve the original
        state.initial_intent = None
        await repo.upsert_chat_snapshot_async(state)

        row: ChatRow | None = await _fetch_row(db_engine, state.session_id)
        assert row is not None
        assert row.initial_intent == EUserIntent.RECOMMEND_SUBURBS.value

    async def test_completed_at_not_overwritten_once_set(self, db_engine: AsyncEngine) -> None:
        state: ConversationStateDTO = _fresh_state()
        state.status = EStatus.REQUIREMENTS_COMPLETE
        repo: SqlAlchemyChatRepository = _make_repo(db_engine)

        await repo.upsert_chat_snapshot_async(state)
        row_after_first: ChatRow | None = await _fetch_row(db_engine, state.session_id)
        assert row_after_first is not None
        first_completed_at = row_after_first.completed_at

        # Second upsert with IN_PROGRESS — completed_at must not be cleared
        state.status = EStatus.IN_PROGRESS
        await repo.upsert_chat_snapshot_async(state)

        row_after_second: ChatRow | None = await _fetch_row(db_engine, state.session_id)
        assert row_after_second is not None
        assert row_after_second.completed_at == first_completed_at

    async def test_conversation_history_not_present_in_db(self, db_engine: AsyncEngine) -> None:
        state: ConversationStateDTO = _fresh_state()
        state.conversation_history = [{"role": "user", "content": "hello"}]
        repo: SqlAlchemyChatRepository = _make_repo(db_engine)

        await repo.upsert_chat_snapshot_async(state)

        row: ChatRow | None = await _fetch_row(db_engine, state.session_id)
        assert row is not None
        assert "conversation_history" not in row.collected_data

    async def test_db_error_is_logged_and_suppressed_not_raised(
        self, db_engine: AsyncEngine
    ) -> None:
        from unittest.mock import AsyncMock, patch

        state: ConversationStateDTO = _fresh_state()
        repo: SqlAlchemyChatRepository = _make_repo(db_engine)

        with patch.object(repo, "_do_upsert_async", AsyncMock(side_effect=RuntimeError("boom"))):
            # Must not raise — exception is logged and suppressed
            await repo.upsert_chat_snapshot_async(state)
