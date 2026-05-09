"""Integration tests for POST /chat — Story S-D."""

from collections.abc import Generator
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

import routers.chat as chat_module
from exceptions import LLMServiceError
from models.conversation_state import ConversationStateDTO


def _build_body(message: str, state: ConversationStateDTO) -> dict[str, object]:
    """Return a JSON-serialisable request body with camelCase state keys."""
    return {"message": message, "state": state.model_dump(by_alias=True)}


@contextmanager
def _mock_llm(
    extracted: dict[str, object] | None = None,
    reply: str = "Next question?",
) -> Generator[tuple[AsyncMock, AsyncMock], None, None]:
    """Patch both LLM methods for a single chat turn.

    chat_with_tools_async → Round 1 extraction (returns dict)
    complete_async        → Round 2 question generation (returns str)
    """
    tools_mock = AsyncMock(return_value=extracted if extracted is not None else {})
    complete_mock = AsyncMock(return_value=reply)
    with (
        patch.object(chat_module._default_llm_client, "chat_with_tools_async", tools_mock),
        patch.object(chat_module._default_llm_client, "complete_async", complete_mock),
    ):
        yield tools_mock, complete_mock


async def test_valid_request_returns_200(
    client_async: AsyncClient, sample_state: ConversationStateDTO
) -> None:
    """POST /chat with a valid payload returns HTTP 200."""
    with _mock_llm():
        response = await client_async.post("/api/v1/chat", json=_build_body("Hi", sample_state))
    assert response.status_code == 200


async def test_response_conforms_to_chat_response_schema(
    client_async: AsyncClient, sample_state: ConversationStateDTO
) -> None:
    """Response body contains reply, extracted, and updatedState keys."""
    with _mock_llm(reply="Hello!"):
        response = await client_async.post("/api/v1/chat", json=_build_body("Hi", sample_state))
    body = response.json()
    assert "reply" in body
    assert "extracted" in body
    assert "updatedState" in body


async def test_conversation_history_updated_after_turn(
    client_async: AsyncClient, sample_state: ConversationStateDTO
) -> None:
    """After one turn, updatedState.conversationHistory contains the user and assistant messages."""
    with _mock_llm(reply="Assistant reply"):
        response = await client_async.post(
            "/api/v1/chat", json=_build_body("User message", sample_state)
        )
    history = response.json()["updatedState"]["conversationHistory"]
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "User message"
    assert history[1]["role"] == "assistant"
    assert history[1]["content"] == "Assistant reply"


async def test_extracted_fields_written_to_collected_data(
    client_async: AsyncClient, sample_state: ConversationStateDTO
) -> None:
    """Extracted property_type is written into updatedState.collectedData.m1."""
    extracted = {"property_type": "house", "min_bedrooms": 3, "intended_use": "owner_occupier"}
    with _mock_llm(extracted=extracted, reply="Got it!"):
        response = await client_async.post(
            "/api/v1/chat", json=_build_body("I want a house", sample_state)
        )
    m1 = response.json()["updatedState"]["collectedData"]["m1"]
    assert m1["property_type"] == "house"


async def test_completion_status_updated_correctly(
    client_async: AsyncClient, sample_state: ConversationStateDTO
) -> None:
    """After a turn that satisfies all M1 required fields, completionStatus.m1 is True."""
    extracted = {"property_type": "house", "min_bedrooms": 2, "intended_use": "owner_occupier"}
    with _mock_llm(extracted=extracted, reply="M1 done!"):
        response = await client_async.post(
            "/api/v1/chat", json=_build_body("3 bed house owner-occupier", sample_state)
        )
    assert response.json()["updatedState"]["completionStatus"]["M1"] is True


async def test_no_tool_call_returns_empty_extracted(
    client_async: AsyncClient, sample_state: ConversationStateDTO
) -> None:
    """When Round 1 LLM returns no tool call, extracted is {} and Round 2 still succeeds."""
    with _mock_llm(extracted={}, reply="Just a reply"):
        response = await client_async.post("/api/v1/chat", json=_build_body("Hello", sample_state))
    assert response.status_code == 200
    assert response.json()["extracted"] == {}


async def test_empty_message_returns_422(
    client_async: AsyncClient, sample_state: ConversationStateDTO
) -> None:
    """An empty message string triggers Pydantic validation and returns HTTP 422."""
    response = await client_async.post("/api/v1/chat", json=_build_body("", sample_state))
    assert response.status_code == 422


async def test_llm_failure_returns_503(
    client_async: AsyncClient, sample_state: ConversationStateDTO
) -> None:
    """An LLMServiceError raised by Round 1 returns HTTP 503 with the error envelope."""
    tools_mock = AsyncMock(side_effect=LLMServiceError("OpenRouter unavailable"))
    with patch.object(chat_module._default_llm_client, "chat_with_tools_async", tools_mock):
        response = await client_async.post("/api/v1/chat", json=_build_body("Hi", sample_state))
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "LLMServiceError"


async def test_history_accumulates_across_turns(
    client_async: AsyncClient, sample_state: ConversationStateDTO
) -> None:
    """Conversation history grows correctly across two sequential turns (4 messages total)."""
    with _mock_llm(reply="Reply"):
        first = await client_async.post("/api/v1/chat", json=_build_body("Turn one", sample_state))
        assert first.status_code == 200

        updated_state = first.json()["updatedState"]
        second = await client_async.post(
            "/api/v1/chat", json={"message": "Turn two", "state": updated_state}
        )
        assert second.status_code == 200

    history = second.json()["updatedState"]["conversationHistory"]
    assert len(history) == 4
    assert history[0]["content"] == "Turn one"
    assert history[2]["content"] == "Turn two"
