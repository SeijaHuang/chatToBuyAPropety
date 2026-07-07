"""Direct unit tests for ChatService — bypasses HTTP entirely (see test_chat_endpoint.py
for integration coverage of the same behaviour through the router)."""

import uuid
from unittest.mock import AsyncMock

import pytest

from db.repositories.chat import IChatRepository
from domain.llm_client import ILLMClient
from exceptions import SessionNotFoundError, SummaryValidationError
from models.conversation_state import (
    CollectedData,
    ConversationStateDTO,
    EPropertyType,
    EUserIntent,
    M1PropertyNeeds,
)
from redis_store.session_store import ISessionStore
from services.chats.chat_service import (
    ChatService,
    ChatTurnResult,
    SessionRestoreResult,
    SummaryResult,
)


@pytest.fixture
def mock_session_store() -> AsyncMock:
    return AsyncMock(spec=ISessionStore)


@pytest.fixture
def mock_chat_repo() -> AsyncMock:
    return AsyncMock(spec=IChatRepository)


@pytest.fixture
def mock_llm_client() -> AsyncMock:
    llm: AsyncMock = AsyncMock(spec=ILLMClient)
    llm.chat_with_tools_async.return_value = {}
    llm.complete_async.return_value = "Next question?"
    return llm


@pytest.fixture
def service(
    mock_session_store: AsyncMock, mock_chat_repo: AsyncMock, mock_llm_client: AsyncMock
) -> ChatService:
    """ChatService wired to its constructor-injected dependencies for these unit tests."""
    return ChatService(
        chat_repo=mock_chat_repo,
        session_store=mock_session_store,
        llm_client=mock_llm_client,
    )


# ---------------------------------------------------------------------------
# process_turn_async
# ---------------------------------------------------------------------------


_TEST_ANON_ID: uuid.UUID = uuid.uuid4()
_VALID_SESSION_ID: str = "11111111-1111-4111-a111-111111111111"
_VALID_SESSION_UUID: uuid.UUID = uuid.UUID(_VALID_SESSION_ID)


async def test_process_turn_generates_session_id_when_none_given(
    mock_session_store: AsyncMock, mock_chat_repo: AsyncMock, service: ChatService
) -> None:
    """A None session_id causes ChatService to generate a fresh UUID v4."""
    mock_session_store.load_session_async.return_value = None

    result: ChatTurnResult = await service.process_turn_async(
        session_id=None, message="Hi", anon_id=_TEST_ANON_ID
    )

    assert result.state.session_id != ""
    assert result.should_persist is True
    mock_chat_repo.upsert_chat_snapshot_async.assert_awaited_once_with(result.state, _TEST_ANON_ID)


async def test_process_turn_marks_should_persist_false_for_continuing_incomplete_session(
    mock_session_store: AsyncMock, mock_chat_repo: AsyncMock, service: ChatService
) -> None:
    """An existing session with no module newly completed does not request persistence."""
    existing: ConversationStateDTO = ConversationStateDTO(session_id=_VALID_SESSION_ID)
    mock_session_store.load_session_async.return_value = existing

    result: ChatTurnResult = await service.process_turn_async(
        session_id=_VALID_SESSION_UUID, message="Hi", anon_id=_TEST_ANON_ID
    )

    assert result.should_persist is False
    assert result.reply == "Next question?"
    mock_chat_repo.upsert_chat_snapshot_async.assert_not_awaited()


async def test_process_turn_appends_user_and_assistant_messages(
    mock_session_store: AsyncMock, service: ChatService
) -> None:
    """Both the user message and the assistant reply are appended to conversation_history."""
    mock_session_store.load_session_async.return_value = None

    result: ChatTurnResult = await service.process_turn_async(
        session_id=_VALID_SESSION_UUID, message="Hello", anon_id=_TEST_ANON_ID
    )

    assert result.state.conversation_history[0] == {"role": "user", "content": "Hello"}
    assert result.state.conversation_history[1] == {
        "role": "assistant",
        "content": "Next question?",
    }
    mock_session_store.save_session_async.assert_awaited_once()


# ---------------------------------------------------------------------------
# restore_session_async
# ---------------------------------------------------------------------------


async def test_restore_session_returns_redis_hit_without_calling_llm(
    mock_session_store: AsyncMock,
    mock_chat_repo: AsyncMock,
    mock_llm_client: AsyncMock,
    service: ChatService,
) -> None:
    """A Redis hit short-circuits before any Postgres or LLM call."""
    existing: ConversationStateDTO = ConversationStateDTO(session_id=_VALID_SESSION_ID)
    mock_session_store.load_session_async.return_value = existing

    result: SessionRestoreResult = await service.restore_session_async(
        session_id=_VALID_SESSION_UUID
    )

    assert result.resume_message is None
    mock_chat_repo.get_chat_snapshot_async.assert_not_awaited()
    mock_llm_client.complete_async.assert_not_awaited()


async def test_restore_session_raises_not_found_when_neither_store_has_it(
    mock_session_store: AsyncMock, mock_chat_repo: AsyncMock, service: ChatService
) -> None:
    """Redis miss + Postgres miss raises SessionNotFoundError."""
    mock_session_store.load_session_async.return_value = None
    mock_chat_repo.get_chat_snapshot_async.return_value = None

    with pytest.raises(SessionNotFoundError):
        await service.restore_session_async(session_id=_VALID_SESSION_UUID)


async def test_restore_session_db_fallback_generates_resume_message(
    mock_session_store: AsyncMock,
    mock_chat_repo: AsyncMock,
    mock_llm_client: AsyncMock,
    service: ChatService,
) -> None:
    """Redis miss + Postgres hit calls the LLM and returns a non-null resume_message."""
    mock_session_store.load_session_async.return_value = None
    mock_chat_repo.get_chat_snapshot_async.return_value = ConversationStateDTO(
        session_id=_VALID_SESSION_ID
    )
    mock_llm_client.complete_async.return_value = "Welcome back!"

    result: SessionRestoreResult = await service.restore_session_async(
        session_id=_VALID_SESSION_UUID
    )

    assert result.resume_message == "Welcome back!"
    assert result.conversation_history == []
    assert result.state.conversation_history[0]["content"] == "Welcome back!"
    mock_session_store.save_session_async.assert_awaited_once()


async def test_restore_session_survives_redis_reseed_failure(
    mock_session_store: AsyncMock,
    mock_chat_repo: AsyncMock,
    mock_llm_client: AsyncMock,
    service: ChatService,
) -> None:
    """A Redis re-seed failure is swallowed — the restore result is still returned."""
    mock_session_store.load_session_async.return_value = None
    mock_chat_repo.get_chat_snapshot_async.return_value = ConversationStateDTO(
        session_id=_VALID_SESSION_ID
    )
    mock_session_store.save_session_async.side_effect = Exception("Redis down")
    mock_llm_client.complete_async.return_value = "Welcome back!"

    result: SessionRestoreResult = await service.restore_session_async(
        session_id=_VALID_SESSION_UUID
    )

    assert result.resume_message == "Welcome back!"


# ---------------------------------------------------------------------------
# generate_summary_async
# ---------------------------------------------------------------------------


async def test_generate_summary_raises_when_all_fields_none(
    mock_llm_client: AsyncMock, service: ChatService
) -> None:
    """An all-None CollectedData raises SummaryValidationError before calling the LLM."""
    with pytest.raises(SummaryValidationError):
        await service.generate_summary_async(
            collected_data=CollectedData(),
            session_id="s1",
            initial_intent=EUserIntent.OPEN_ENDED_QUERY,
        )
    mock_llm_client.complete_async.assert_not_awaited()


async def test_generate_summary_returns_summary_and_user_needs(
    mock_llm_client: AsyncMock, service: ChatService
) -> None:
    """Non-empty CollectedData produces a SummaryResult with the LLM's reply and UserNeeds."""
    mock_llm_client.complete_async.return_value = "You're looking for a 3-bedroom house."
    data: CollectedData = CollectedData(
        m1=M1PropertyNeeds(property_type=EPropertyType.HOUSE, min_bedrooms=3)
    )

    result: SummaryResult = await service.generate_summary_async(
        collected_data=data,
        session_id="s1",
        initial_intent=EUserIntent.OPEN_ENDED_QUERY,
    )

    assert result.summary_text == "You're looking for a 3-bedroom house."
    assert result.user_needs.session_id == "s1"
    assert result.user_needs.collected.m1.property_type == "house"
