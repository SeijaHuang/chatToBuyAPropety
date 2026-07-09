"""Unit tests for SqlAlchemy repository implementations — no live database required.

These tests mock the SQLAlchemy async session factory so every code path in
chat.py and user.py is exercised without a PostgreSQL connection.
The companion test_chat_repository.py covers the same code against a real DB.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from db.repositories.chat import SqlAlchemyChatRepository
from db.repositories.user import SqlAlchemyUserRepository
from models.shared.conversation_state import ConversationStateDTO
from models.shared.enums import EStatus, EUserIntent

TEST_ANON_ID: str = "aaaabbbb-cccc-4000-aaaa-bbbbbbbbbbbb"


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------


def _make_session_factory() -> tuple[MagicMock, AsyncMock]:
    """Return (factory, session) where factory() is an async context manager yielding session."""
    mock_session: AsyncMock = AsyncMock()
    mock_cm: AsyncMock = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    mock_factory: MagicMock = MagicMock(return_value=mock_cm)
    return mock_factory, mock_session


def _fresh_state() -> ConversationStateDTO:
    return ConversationStateDTO(session_id=str(uuid.uuid4()))


# ---------------------------------------------------------------------------
# SqlAlchemyUserRepository
# ---------------------------------------------------------------------------


class TestSqlAlchemyUserRepository:
    """SqlAlchemyUserRepository"""

    async def test_get_or_create_with_none_creates_new_user(self) -> None:
        factory, session = _make_session_factory()
        session.execute = AsyncMock()
        repo: SqlAlchemyUserRepository = SqlAlchemyUserRepository(factory)

        result: uuid.UUID = await repo.get_or_create_async(None)

        assert isinstance(result, uuid.UUID)

    async def test_get_or_create_with_existing_anon_id_returns_same_id(self) -> None:
        factory, session = _make_session_factory()
        anon_uuid: uuid.UUID = uuid.UUID(TEST_ANON_ID)
        select_result: MagicMock = MagicMock()
        select_result.scalar_one_or_none.return_value = anon_uuid
        update_result: MagicMock = MagicMock()
        session.execute = AsyncMock(side_effect=[select_result, update_result])
        repo: SqlAlchemyUserRepository = SqlAlchemyUserRepository(factory)

        result: uuid.UUID = await repo.get_or_create_async(anon_uuid)

        assert result == anon_uuid

    async def test_get_or_create_with_unknown_uuid_creates_new_user(self) -> None:
        factory, session = _make_session_factory()
        select_result: MagicMock = MagicMock()
        select_result.scalar_one_or_none.return_value = None
        insert_result: MagicMock = MagicMock()
        session.execute = AsyncMock(side_effect=[select_result, insert_result])
        repo: SqlAlchemyUserRepository = SqlAlchemyUserRepository(factory)

        result: uuid.UUID = await repo.get_or_create_async(uuid.uuid4())

        assert isinstance(result, uuid.UUID)

    async def test_create_new_async_returns_uuid(self) -> None:
        factory, session = _make_session_factory()
        session.execute = AsyncMock()
        repo: SqlAlchemyUserRepository = SqlAlchemyUserRepository(factory)

        result: uuid.UUID = await repo._create_new_async()

        assert isinstance(result, uuid.UUID)

    async def test_touch_existing_returns_none_when_user_not_found(self) -> None:
        factory, session = _make_session_factory()
        select_result: MagicMock = MagicMock()
        select_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=select_result)
        repo: SqlAlchemyUserRepository = SqlAlchemyUserRepository(factory)

        result: uuid.UUID | None = await repo._touch_existing_async(uuid.UUID(TEST_ANON_ID))

        assert result is None


# ---------------------------------------------------------------------------
# SqlAlchemyChatRepository
# ---------------------------------------------------------------------------


class TestSqlAlchemyChatRepository:
    """SqlAlchemyChatRepository"""

    async def test_upsert_suppresses_exception_from_do_upsert(self) -> None:
        factory, _ = _make_session_factory()
        repo: SqlAlchemyChatRepository = SqlAlchemyChatRepository(factory)
        state: ConversationStateDTO = _fresh_state()

        with patch.object(repo, "_do_upsert_async", AsyncMock(side_effect=RuntimeError("boom"))):
            await repo.upsert_chat_snapshot_async(state, uuid.UUID(TEST_ANON_ID))

    async def test_upsert_delegates_to_do_upsert(self) -> None:
        factory, _ = _make_session_factory()
        repo: SqlAlchemyChatRepository = SqlAlchemyChatRepository(factory)
        state: ConversationStateDTO = _fresh_state()
        mock_do_upsert: AsyncMock = AsyncMock()

        with patch.object(repo, "_do_upsert_async", mock_do_upsert):
            await repo.upsert_chat_snapshot_async(state, uuid.UUID(TEST_ANON_ID))

        mock_do_upsert.assert_awaited_once_with(state, uuid.UUID(TEST_ANON_ID))

    async def test_do_upsert_executes_and_commits(self) -> None:
        factory, session = _make_session_factory()
        repo: SqlAlchemyChatRepository = SqlAlchemyChatRepository(factory)
        state: ConversationStateDTO = _fresh_state()

        await repo._do_upsert_async(state, uuid.UUID(TEST_ANON_ID))

        session.execute.assert_awaited_once()
        session.commit.assert_awaited_once()

    async def test_do_upsert_with_complete_status(self) -> None:
        factory, session = _make_session_factory()
        repo: SqlAlchemyChatRepository = SqlAlchemyChatRepository(factory)
        state: ConversationStateDTO = _fresh_state()
        state.status = EStatus.REQUIREMENTS_COMPLETE

        await repo._do_upsert_async(state, uuid.UUID(TEST_ANON_ID))

        session.execute.assert_awaited_once()

    async def test_do_upsert_with_initial_intent(self) -> None:
        factory, session = _make_session_factory()
        repo: SqlAlchemyChatRepository = SqlAlchemyChatRepository(factory)
        state: ConversationStateDTO = _fresh_state()
        state.initial_intent = EUserIntent.RECOMMEND_SUBURBS

        await repo._do_upsert_async(state, uuid.UUID(TEST_ANON_ID))

        session.execute.assert_awaited_once()

    async def test_do_upsert_with_borrowing_capacity(self) -> None:
        from models.shared.financial import BorrowingCapacityResult

        factory, session = _make_session_factory()
        repo: SqlAlchemyChatRepository = SqlAlchemyChatRepository(factory)
        state: ConversationStateDTO = _fresh_state()
        state.borrowing_capacity = BorrowingCapacityResult(
            estimated_capacity=500_000,
            monthly_repayment=2_000,
            based_on_salary=120_000,
            is_joint=False,
            annual_rate=6.0,
            loan_term_years=25,
            rate_source="RBA",
            disclaimer="Estimate only.",
        )

        await repo._do_upsert_async(state, uuid.UUID(TEST_ANON_ID))

        session.execute.assert_awaited_once()

    async def test_list_chats_returns_empty_when_no_rows(self) -> None:
        factory, session = _make_session_factory()
        select_result: MagicMock = MagicMock()
        select_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=select_result)
        repo: SqlAlchemyChatRepository = SqlAlchemyChatRepository(factory)

        result = await repo.list_chats_by_anon_async(uuid.UUID(TEST_ANON_ID))

        assert result == []

    async def test_list_chats_maps_rows_to_dtos(self) -> None:
        factory, session = _make_session_factory()
        session_id: uuid.UUID = uuid.uuid4()
        now: datetime = datetime.now(tz=UTC)

        mock_row: MagicMock = MagicMock()
        mock_row.session_id = session_id
        mock_row.status = EStatus.IN_PROGRESS
        mock_row.initial_intent = None
        mock_row.created_at = now
        mock_row.updated_at = now
        mock_row.completed_at = None

        select_result: MagicMock = MagicMock()
        select_result.scalars.return_value.all.return_value = [mock_row]
        session.execute = AsyncMock(return_value=select_result)
        repo: SqlAlchemyChatRepository = SqlAlchemyChatRepository(factory)

        result = await repo.list_chats_by_anon_async(uuid.UUID(TEST_ANON_ID))

        assert len(result) == 1
        assert result[0].session_id == str(session_id)
        assert result[0].status == EStatus.IN_PROGRESS
        assert result[0].completed_at is None
