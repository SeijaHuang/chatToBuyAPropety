"""Tests for routers/chat.py POST /chat/summary endpoint — Story S-F."""

from typing import Any
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

import routers.chat as chat_module
from models.conversation_state import CollectedData, M1PropertyNeeds, M3SuburbPreference, M4Budget

_MOCK_SUMMARY = "Budget max is 800000, property type is house, commute to CBD"


def _make_collected_data() -> CollectedData:
    return CollectedData(
        m1=M1PropertyNeeds(property_type="house", min_bedrooms=3),
        m3=M3SuburbPreference(commute_destination="CBD"),
        m4=M4Budget(budget_max=800000),
    )


def _summary_payload(data: CollectedData | None = None) -> dict[str, Any]:
    cd = data or _make_collected_data()
    return {"collectedData": cd.model_dump(mode="json")}


async def test_valid_request_returns_200(client_async: AsyncClient) -> None:
    mock = AsyncMock(return_value=_MOCK_SUMMARY)
    with patch.object(chat_module._default_llm_client, "complete_async", mock):
        response = await client_async.post("/api/v1/chat/summary", json=_summary_payload())
    assert response.status_code == 200


async def test_summary_text_is_nonempty_string(client_async: AsyncClient) -> None:
    mock = AsyncMock(return_value=_MOCK_SUMMARY)
    with patch.object(chat_module._default_llm_client, "complete_async", mock):
        response = await client_async.post("/api/v1/chat/summary", json=_summary_payload())
    body = response.json()
    assert isinstance(body["summaryText"], str)
    assert len(body["summaryText"]) > 0


async def test_summary_contains_budget_max(client_async: AsyncClient) -> None:
    mock = AsyncMock(return_value=_MOCK_SUMMARY)
    with patch.object(chat_module._default_llm_client, "complete_async", mock):
        response = await client_async.post("/api/v1/chat/summary", json=_summary_payload())
    assert "800000" in response.json()["summaryText"]


async def test_summary_contains_property_type(client_async: AsyncClient) -> None:
    mock = AsyncMock(return_value=_MOCK_SUMMARY)
    with patch.object(chat_module._default_llm_client, "complete_async", mock):
        response = await client_async.post("/api/v1/chat/summary", json=_summary_payload())
    assert "house" in response.json()["summaryText"]


async def test_summary_contains_commute_destination(client_async: AsyncClient) -> None:
    mock = AsyncMock(return_value=_MOCK_SUMMARY)
    with patch.object(chat_module._default_llm_client, "complete_async", mock):
        response = await client_async.post("/api/v1/chat/summary", json=_summary_payload())
    assert "CBD" in response.json()["summaryText"]


async def test_structured_field_unchanged(client_async: AsyncClient) -> None:
    data = _make_collected_data()
    mock = AsyncMock(return_value=_MOCK_SUMMARY)
    with patch.object(chat_module._default_llm_client, "complete_async", mock):
        response = await client_async.post("/api/v1/chat/summary", json=_summary_payload(data))
    assert response.status_code == 200
    structured = response.json()["structured"]
    round_tripped = CollectedData.model_validate(structured)
    assert round_tripped == data


async def test_all_none_fields_returns_422(client_async: AsyncClient) -> None:
    empty_payload = {"collectedData": CollectedData().model_dump(mode="json")}
    mock = AsyncMock(return_value=_MOCK_SUMMARY)
    with patch.object(chat_module._default_llm_client, "complete_async", mock):
        response = await client_async.post("/api/v1/chat/summary", json=empty_payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SummaryValidationError"
