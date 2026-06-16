"""Integration tests for POST /chat and GET /session — P1-A Redis session store."""

import json
from collections.abc import AsyncGenerator, Generator
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

import routers.chat as chat_module
from domain.redis import session_store as session_store_module
from exceptions import LLMServiceError, RateLimitError
from models.conversation_state import ConversationStateDTO

_SESSION_ID: str = "test-session-001"


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
    """Response body contains reply and extracted keys; no updatedState (server-managed)."""
    with _mock_session(), _mock_llm(reply="Hello!"):
        response = await client_async.post("/api/v1/chat", json=_build_body("Hi"))
    data: dict[str, object] = response.json()["data"]
    assert "reply" in data
    assert "extracted" in data
    assert "updatedState" not in data


async def test_no_tool_call_returns_empty_extracted(client_async: AsyncClient) -> None:
    """When Round 1 LLM returns no tool call, extracted is {} and Round 2 still succeeds."""
    with _mock_session(), _mock_llm(extracted={}, reply="Just a reply"):
        response = await client_async.post("/api/v1/chat", json=_build_body("Hello"))
    assert response.status_code == 200
    assert response.json()["data"]["extracted"] == {}


# ---------------------------------------------------------------------------
# Auto-create new session on first message
# ---------------------------------------------------------------------------


async def test_auto_creates_session_on_first_message(client_async: AsyncClient) -> None:
    """A new session is created automatically when the session_id is not in Redis."""
    with _mock_session() as store, _mock_llm():
        response = await client_async.post("/api/v1/chat", json=_build_body("Hi"))
    assert response.status_code == 200
    assert _SESSION_ID in store


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
# GET /session/{session_id}
# ---------------------------------------------------------------------------


async def test_get_session_returns_stored_state(client_async: AsyncClient) -> None:
    """GET /session/{id} returns the current session state from Redis."""
    initial: ConversationStateDTO = ConversationStateDTO(session_id=_SESSION_ID)
    with _mock_session(initial=initial):
        response = await client_async.get(f"/api/v1/session/{_SESSION_ID}")
    assert response.status_code == 200
    assert response.json()["data"]["sessionId"] == _SESSION_ID


async def test_get_session_404_when_not_found(client_async: AsyncClient) -> None:
    """GET /session/{id} returns 404 when the session_id is absent from Redis."""
    with _mock_session():
        response = await client_async.get("/api/v1/session/nonexistent-session")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SessionNotFoundError"


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


async def test_empty_message_returns_422(client_async: AsyncClient) -> None:
    """An empty message string triggers Pydantic validation and returns HTTP 422."""
    response = await client_async.post("/api/v1/chat", json=_build_body(""))
    assert response.status_code == 422


async def test_missing_session_id_returns_422(client_async: AsyncClient) -> None:
    """A request without sessionId triggers Pydantic validation and returns HTTP 422."""
    response = await client_async.post("/api/v1/chat", json={"message": "Hi"})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# LLM error propagation
# ---------------------------------------------------------------------------


async def test_llm_failure_returns_503(client_async: AsyncClient) -> None:
    """An LLMServiceError raised by Round 1 returns HTTP 503 with the error envelope."""
    tools_mock: AsyncMock = AsyncMock(side_effect=LLMServiceError("OpenRouter unavailable"))
    with _mock_session(), patch.object(
        chat_module._default_llm_client, "chat_with_tools_async", tools_mock
    ):
        response = await client_async.post("/api/v1/chat", json=_build_body("Hi"))
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "LLMServiceError"


async def test_rate_limit_returns_429(client_async: AsyncClient) -> None:
    """A RateLimitError raised by Round 1 returns HTTP 429 with retry_after in details."""
    tools_mock: AsyncMock = AsyncMock(side_effect=RateLimitError())
    with _mock_session(), patch.object(
        chat_module._default_llm_client, "chat_with_tools_async", tools_mock
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