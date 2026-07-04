"""Integration tests for POST /chat and GET /session — P1-A Redis session store."""

import json
import re
from collections.abc import Generator
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

import routers.chat as chat_module
from exceptions import LLMServiceError, RateLimitError
from models.conversation_state import ConversationStateDTO
from models.financial import BorrowingCapacityResult
from redis_store import session_store as session_store_module

_SESSION_ID: str = "test-session-001"
_VALID_SESSION_UUID: str = "11111111-1111-4111-a111-111111111111"

_UUID4_PATTERN: re.Pattern[str] = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _build_body(message: str, session_id: str = _SESSION_ID) -> dict[str, object]:
    """Return a JSON-serialisable request body for the new Redis-backed API."""
    return {"sessionId": session_id, "message": message}


@contextmanager
def _mock_llm(
    extracted: dict[str, object] | None = None,
    reply: str = "Next question?",
) -> Generator[tuple[AsyncMock, AsyncMock], None, None]:
    """Patch both LLM methods for a single chat turn."""
    tools_mock = AsyncMock(return_value=extracted if extracted is not None else {})
    complete_mock = AsyncMock(return_value=reply)
    with (
        patch.object(chat_module._default_llm_client, "chat_with_tools_async", tools_mock),
        patch.object(chat_module._default_llm_client, "complete_async", complete_mock),
    ):
        yield tools_mock, complete_mock


@contextmanager
def _mock_session(
    initial: ConversationStateDTO | None = None,
) -> Generator[dict[str, ConversationStateDTO], None, None]:
    """Simulate Redis session persistence with an in-memory dict.

    Provides load/save mocks that share a dict so callers can inspect saved state
    and simulate state persistence across multiple turns within a single test.
    """
    store: dict[str, ConversationStateDTO] = {}
    if initial is not None:
        store[initial.session_id] = initial

    async def _load(session_id: str) -> ConversationStateDTO | None:
        return store.get(session_id)

    async def _save(state: ConversationStateDTO) -> None:
        store[state.session_id] = state

    with (
        patch.object(session_store_module.session_store, "load_session_async", _load),
        patch.object(session_store_module.session_store, "save_session_async", _save),
    ):
        yield store


# ---------------------------------------------------------------------------
# Basic contract
# ---------------------------------------------------------------------------


async def test_valid_request_returns_200(client_async: AsyncClient) -> None:
    """POST /chat with a valid payload returns HTTP 200."""
    with _mock_session(), _mock_llm():
        response = await client_async.post("/api/v1/chat", json=_build_body("Hi"))
    assert response.status_code == 200


async def test_response_conforms_to_chat_response_schema(client_async: AsyncClient) -> None:
    """Response body contains reply, extracted, sessionId, and state; anonId moved to cookie."""
    with _mock_session(), _mock_llm(reply="Hello!"):
        response = await client_async.post("/api/v1/chat", json=_build_body("Hi"))
    data: dict[str, object] = response.json()["data"]
    assert "reply" in data
    assert "extracted" in data
    assert "sessionId" in data
    assert "anonId" not in data
    assert "state" in data
    assert "updatedState" not in data
    assert "propertyai_anon_id" in response.cookies


async def test_no_tool_call_returns_empty_extracted(client_async: AsyncClient) -> None:
    """When Round 1 LLM returns no tool call, extracted is {} and Round 2 still succeeds."""
    with _mock_session(), _mock_llm(extracted={}, reply="Just a reply"):
        response = await client_async.post("/api/v1/chat", json=_build_body("Hello"))
    assert response.status_code == 200
    assert response.json()["data"]["extracted"] == {}


# ---------------------------------------------------------------------------
# session_id generation and reuse
# ---------------------------------------------------------------------------


async def test_auto_creates_session_on_first_message(client_async: AsyncClient) -> None:
    """A new session is created automatically when the session_id is not in Redis."""
    with _mock_session() as store, _mock_llm():
        response = await client_async.post("/api/v1/chat", json=_build_body("Hi"))
    assert response.status_code == 200
    assert _SESSION_ID in store


async def test_omitting_session_id_generates_uuid_v4(client_async: AsyncClient) -> None:
    """Omitting session_id causes the backend to generate a UUID v4 and return it."""
    with _mock_session(), _mock_llm():
        response = await client_async.post("/api/v1/chat", json={"message": "Hi"})
    assert response.status_code == 200
    returned_id: object = response.json()["data"]["sessionId"]
    assert isinstance(returned_id, str)
    assert _UUID4_PATTERN.match(returned_id), f"Not a UUID v4: {returned_id}"


async def test_omitting_session_id_response_state_has_no_conversation_history(
    client_async: AsyncClient,
) -> None:
    """When session_id is omitted, the returned state snapshot excludes conversationHistory."""
    with _mock_session(), _mock_llm():
        response = await client_async.post("/api/v1/chat", json={"message": "Hi"})
    state: object = response.json()["data"]["state"]
    assert isinstance(state, dict)
    assert "conversationHistory" not in state
    assert "conversation_history" not in state


async def test_sending_existing_session_id_reuses_session(client_async: AsyncClient) -> None:
    """When session_id matches a stored session, that session is loaded and its id echoed back."""
    existing: ConversationStateDTO = ConversationStateDTO(session_id=_SESSION_ID)
    with _mock_session(initial=existing), _mock_llm():
        response = await client_async.post("/api/v1/chat", json=_build_body("Hi"))
    assert response.status_code == 200
    assert response.json()["data"]["sessionId"] == _SESSION_ID


# ---------------------------------------------------------------------------
# State persistence across turns
# ---------------------------------------------------------------------------


async def test_history_accumulates_across_turns(client_async: AsyncClient) -> None:
    """Conversation history grows to 4 messages across two sequential turns."""
    with _mock_session() as store, _mock_llm(reply="Reply"):
        await client_async.post("/api/v1/chat", json=_build_body("Turn one"))
        assert len(store[_SESSION_ID].conversation_history) == 2

        response = await client_async.post("/api/v1/chat", json=_build_body("Turn two"))
        assert response.status_code == 200

    history = store[_SESSION_ID].conversation_history
    assert len(history) == 4
    assert history[0]["content"] == "Turn one"
    assert history[2]["content"] == "Turn two"


async def test_extracted_fields_written_to_collected_data(client_async: AsyncClient) -> None:
    """Extracted property_type is persisted into the session's collected_data.m1."""
    extracted: dict[str, object] = {
        "property_type": "house",
        "min_bedrooms": 3,
        "intended_use": "owner_occupier",
    }
    with _mock_session() as store, _mock_llm(extracted=extracted, reply="Got it!"):
        response = await client_async.post("/api/v1/chat", json=_build_body("I want a house"))
    assert response.status_code == 200
    assert store[_SESSION_ID].collected_data.m1.property_type == "house"


async def test_completion_status_updated_in_session(client_async: AsyncClient) -> None:
    """After a turn that satisfies all M1 required fields, the saved session shows M1 complete."""
    extracted: dict[str, object] = {
        "property_type": "house",
        "min_bedrooms": 2,
        "intended_use": "owner_occupier",
    }
    with _mock_session() as store, _mock_llm(extracted=extracted, reply="M1 done!"):
        await client_async.post("/api/v1/chat", json=_build_body("3 bed house owner-occupier"))
    assert store[_SESSION_ID].completion_status.M1 is True


# ---------------------------------------------------------------------------
# ChatResponse.state snapshot
# ---------------------------------------------------------------------------


async def test_chat_response_state_does_not_include_conversation_history(
    client_async: AsyncClient,
) -> None:
    """The state snapshot in ChatResponse never contains conversationHistory."""
    with _mock_session(), _mock_llm():
        response = await client_async.post("/api/v1/chat", json=_build_body("Hi"))
    state: object = response.json()["data"]["state"]
    assert isinstance(state, dict)
    assert "conversationHistory" not in state
    assert "conversation_history" not in state


async def test_chat_response_state_contains_current_module(client_async: AsyncClient) -> None:
    """The state snapshot in ChatResponse includes currentModule."""
    with _mock_session(), _mock_llm():
        response = await client_async.post("/api/v1/chat", json=_build_body("Hi"))
    state: dict[str, object] = response.json()["data"]["state"]
    assert "currentModule" in state


# ---------------------------------------------------------------------------
# GET /chat/{session_id}
# ---------------------------------------------------------------------------


async def test_get_session_returns_stored_state(client_async: AsyncClient) -> None:
    """GET /chat/{id} returns resume_message=None and state snapshot on Redis hit."""
    initial: ConversationStateDTO = ConversationStateDTO(session_id=_VALID_SESSION_UUID)
    with _mock_session(initial=initial):
        response = await client_async.get(f"/api/v1/chat/{_VALID_SESSION_UUID}")
    assert response.status_code == 200
    data: dict[str, object] = response.json()["data"]
    assert data["resumeMessage"] is None
    state: dict[str, object] = response.json()["data"]["state"]
    assert state["sessionId"] == _VALID_SESSION_UUID


async def test_get_session_404_when_not_found(client_async: AsyncClient) -> None:
    """GET /chat/{id} returns 404 when the session is absent from both Redis and DB."""
    _absent_uuid: str = "22222222-2222-4222-a222-222222222222"
    with _mock_session():
        response = await client_async.get(f"/api/v1/chat/{_absent_uuid}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SessionNotFoundError"


async def test_get_session_db_restore_returns_resume_message(client_async: AsyncClient) -> None:
    """GET /chat/{id} calls the LLM and returns a non-null resumeMessage on Redis miss + DB hit."""
    from db.repositories.chat import get_chat_repository
    from main import app

    db_state: ConversationStateDTO = ConversationStateDTO(session_id=_VALID_SESSION_UUID)
    mock_repo: AsyncMock = app.dependency_overrides[get_chat_repository]()
    mock_repo.get_chat_snapshot_async.return_value = db_state

    complete_mock: AsyncMock = AsyncMock(return_value="Welcome back!")
    with (
        _mock_session(),
        patch.object(chat_module._default_llm_client, "complete_async", complete_mock),
    ):
        response = await client_async.get(f"/api/v1/chat/{_VALID_SESSION_UUID}")

    assert response.status_code == 200
    data: dict[str, object] = response.json()["data"]
    assert data["resumeMessage"] == "Welcome back!"
    assert data["conversationHistory"] == []


async def test_get_session_db_restore_reseeds_redis(client_async: AsyncClient) -> None:
    """After DB restore, the reconstructed state with welcome message is saved back to Redis."""
    from db.repositories.chat import get_chat_repository
    from main import app

    db_state: ConversationStateDTO = ConversationStateDTO(session_id=_VALID_SESSION_UUID)
    mock_repo: AsyncMock = app.dependency_overrides[get_chat_repository]()
    mock_repo.get_chat_snapshot_async.return_value = db_state

    complete_mock: AsyncMock = AsyncMock(return_value="Welcome back!")
    with (
        _mock_session() as store,
        patch.object(chat_module._default_llm_client, "complete_async", complete_mock),
    ):
        response = await client_async.get(f"/api/v1/chat/{_VALID_SESSION_UUID}")

    assert response.status_code == 200
    assert _VALID_SESSION_UUID in store
    assert store[_VALID_SESSION_UUID].conversation_history[0]["content"] == "Welcome back!"


async def test_get_session_db_restore_survives_redis_reseed_failure(
    client_async: AsyncClient,
) -> None:
    """DB restore returns 200 and resumeMessage even when the Redis re-seed call raises."""
    from db.repositories.chat import get_chat_repository
    from main import app

    db_state: ConversationStateDTO = ConversationStateDTO(session_id=_VALID_SESSION_UUID)
    mock_repo: AsyncMock = app.dependency_overrides[get_chat_repository]()
    mock_repo.get_chat_snapshot_async.return_value = db_state

    complete_mock: AsyncMock = AsyncMock(return_value="Welcome back!")
    with (
        _mock_session(),
        patch.object(
            session_store_module.session_store,
            "save_session_async",
            AsyncMock(side_effect=Exception("Redis down")),
        ),
        patch.object(chat_module._default_llm_client, "complete_async", complete_mock),
    ):
        response = await client_async.get(f"/api/v1/chat/{_VALID_SESSION_UUID}")

    assert response.status_code == 200
    assert response.json()["data"]["resumeMessage"] == "Welcome back!"


async def test_get_session_invalid_uuid_returns_400(client_async: AsyncClient) -> None:
    """GET /chat/{id} with a non-UUID segment returns 400 with BadRequestError code."""
    response = await client_async.get("/api/v1/chat/not-a-uuid")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BadRequestError"


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


async def test_empty_message_returns_422(client_async: AsyncClient) -> None:
    """An empty message string triggers Pydantic validation and returns HTTP 422."""
    response = await client_async.post("/api/v1/chat", json=_build_body(""))
    assert response.status_code == 422


async def test_omitting_session_id_is_valid(client_async: AsyncClient) -> None:
    """A request without sessionId is valid — session_id is optional and backend-generated."""
    with _mock_session(), _mock_llm():
        response = await client_async.post("/api/v1/chat", json={"message": "Hi"})
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# LLM error propagation
# ---------------------------------------------------------------------------


async def test_llm_failure_returns_503(client_async: AsyncClient) -> None:
    """An LLMServiceError raised by Round 1 returns HTTP 503 with the error envelope."""
    tools_mock: AsyncMock = AsyncMock(side_effect=LLMServiceError("OpenRouter unavailable"))
    with (
        _mock_session(),
        patch.object(chat_module._default_llm_client, "chat_with_tools_async", tools_mock),
    ):
        response = await client_async.post("/api/v1/chat", json=_build_body("Hi"))
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "LLMServiceError"


async def test_rate_limit_returns_429(client_async: AsyncClient) -> None:
    """A RateLimitError raised by Round 1 returns HTTP 429 with retry_after in details."""
    tools_mock: AsyncMock = AsyncMock(side_effect=RateLimitError())
    with (
        _mock_session(),
        patch.object(chat_module._default_llm_client, "chat_with_tools_async", tools_mock),
    ):
        response = await client_async.post("/api/v1/chat", json=_build_body("Hi"))
    assert response.status_code == 429
    assert response.json()["error"]["details"]["retry_after"] == 2


async def test_tool_call_parse_failure_returns_empty_extracted(client_async: AsyncClient) -> None:
    """A JSONDecodeError from Round 1 is swallowed; response is 200 with empty extracted."""
    tools_mock: AsyncMock = AsyncMock(side_effect=json.JSONDecodeError("bad json", "", 0))
    complete_mock: AsyncMock = AsyncMock(return_value="What are your needs?")
    with (
        _mock_session(),
        patch.object(chat_module._default_llm_client, "chat_with_tools_async", tools_mock),
        patch.object(chat_module._default_llm_client, "complete_async", complete_mock),
    ):
        response = await client_async.post("/api/v1/chat", json=_build_body("Hi"))
    assert response.status_code == 200
    assert response.json()["data"]["extracted"] == {}


# ---------------------------------------------------------------------------
# Borrowing capacity and suburb fallback
# ---------------------------------------------------------------------------


async def test_borrowing_capacity_computed_when_salary_extracted(client_async: AsyncClient) -> None:
    """When pre_tax_salary is extracted, estimate_borrowing_capacity_async is called."""
    extracted: dict[str, object] = {"pre_tax_salary": 100_000}
    mock_result: BorrowingCapacityResult = BorrowingCapacityResult(
        estimated_capacity=560_000,
        monthly_repayment=2_333,
        based_on_salary=100_000,
        is_joint=False,
        annual_rate=6.30,
        loan_term_years=30,
        rate_source="standard variable rate",
        disclaimer="This is an estimate only.",
    )
    with (
        _mock_session(),
        _mock_llm(extracted=extracted, reply="Got your salary!"),
        patch(
            "services.chats.chat_service.estimate_borrowing_capacity_async",
            AsyncMock(return_value=mock_result),
        ),
    ):
        response = await client_async.post("/api/v1/chat", json=_build_body("I earn 100k"))
    assert response.status_code == 200


async def test_commute_destination_used_as_fallback_suburb(client_async: AsyncClient) -> None:
    """When preferred_suburbs is empty but commute_destination is set, it fills gap_suburbs."""
    extracted: dict[str, object] = {"commute_destination": "CBD"}
    with _mock_session(), _mock_llm(extracted=extracted, reply="Got your commute."):
        response = await client_async.post("/api/v1/chat", json=_build_body("I commute to CBD"))
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /chats
# ---------------------------------------------------------------------------


async def test_list_chats_returns_empty_list_for_valid_anon_id(client_async: AsyncClient) -> None:
    """GET /chats returns an empty list when the anon user has no persisted sessions."""
    response = await client_async.get("/api/v1/chats")
    assert response.status_code == 200
    assert response.json()["data"] == []


# ---------------------------------------------------------------------------
# DB upsert trigger — new session vs. subsequent message
# ---------------------------------------------------------------------------


async def test_first_message_on_new_session_triggers_db_upsert(client_async: AsyncClient) -> None:
    """A new session's first message schedules a DB upsert even before any module completes."""
    from db.repositories.chat import get_chat_repository
    from main import app

    mock_repo: AsyncMock = app.dependency_overrides[get_chat_repository]()
    mock_repo.upsert_chat_snapshot_async.reset_mock()

    with _mock_session(), _mock_llm():
        response = await client_async.post("/api/v1/chat", json=_build_body("Hi"))
    assert response.status_code == 200
    mock_repo.upsert_chat_snapshot_async.assert_called_once()


async def test_subsequent_message_without_module_completion_does_not_trigger_db_upsert(
    client_async: AsyncClient,
) -> None:
    """Sending a message to an existing session without completing a module skips DB upsert."""
    from db.repositories.chat import get_chat_repository
    from main import app

    mock_repo: AsyncMock = app.dependency_overrides[get_chat_repository]()
    mock_repo.upsert_chat_snapshot_async.reset_mock()

    existing: ConversationStateDTO = ConversationStateDTO(session_id=_SESSION_ID)
    with _mock_session(initial=existing), _mock_llm():
        response = await client_async.post("/api/v1/chat", json=_build_body("Hi"))
    assert response.status_code == 200
    mock_repo.upsert_chat_snapshot_async.assert_not_called()
