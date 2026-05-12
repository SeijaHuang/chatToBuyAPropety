"""Tests for routers/chat.py POST /chat/summary endpoint — Story S-F."""

from typing import Any
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

import routers.chat as chat_module
from models.conversation_state import (
    CollectedData,
    M1PropertyNeeds,
    M2Lifestyle,
    M3SuburbPreference,
    M4Budget,
)

_MOCK_SUMMARY = "Budget max is 800000, property type is house, commute to CBD"
_SESSION_ID = "test-session-123"


def _make_collected_data() -> CollectedData:
    return CollectedData(
        m1=M1PropertyNeeds(property_type="house", min_bedrooms=3),
        m3=M3SuburbPreference(commute_destination="CBD"),
        m4=M4Budget(budget_max=800000),
    )


def _summary_payload(data: CollectedData | None = None) -> dict[str, Any]:
    cd = data or _make_collected_data()
    return {
        "collectedData": cd.model_dump(mode="json"),
        "sessionId": _SESSION_ID,
    }


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


async def test_structured_schema_version(client_async: AsyncClient) -> None:
    mock = AsyncMock(return_value=_MOCK_SUMMARY)
    with patch.object(chat_module._default_llm_client, "complete_async", mock):
        response = await client_async.post("/api/v1/chat/summary", json=_summary_payload())
    assert response.status_code == 200
    assert response.json()["structured"]["schemaVersion"] == "1.1"


async def test_all_none_fields_returns_422(client_async: AsyncClient) -> None:
    empty_payload = {
        "collectedData": CollectedData().model_dump(mode="json"),
        "sessionId": _SESSION_ID,
    }
    mock = AsyncMock(return_value=_MOCK_SUMMARY)
    with patch.object(chat_module._default_llm_client, "complete_async", mock):
        response = await client_async.post("/api/v1/chat/summary", json=empty_payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SummaryValidationError"


async def test_structured_contains_inferred_needs(client_async: AsyncClient) -> None:
    mock = AsyncMock(return_value=_MOCK_SUMMARY)
    with patch.object(chat_module._default_llm_client, "complete_async", mock):
        response = await client_async.post("/api/v1/chat/summary", json=_summary_payload())
    assert response.status_code == 200
    structured = response.json()["structured"]
    assert "inferred" in structured
    assert "buyerType" in structured["inferred"]


async def test_inferred_buyer_type_owner_occupier(client_async: AsyncClient) -> None:
    data = CollectedData(
        m1=M1PropertyNeeds(property_type="house", min_bedrooms=2, intended_use="owner_occupier"),
        m4=M4Budget(budget_max=600000),
    )
    mock = AsyncMock(return_value=_MOCK_SUMMARY)
    with patch.object(chat_module._default_llm_client, "complete_async", mock):
        response = await client_async.post("/api/v1/chat/summary", json=_summary_payload(data))
    assert response.status_code == 200
    assert response.json()["structured"]["inferred"]["buyerType"] == "owner_occupier"


async def test_inferred_budget_tier_entry(client_async: AsyncClient) -> None:
    data = CollectedData(
        m1=M1PropertyNeeds(property_type="unit", min_bedrooms=1),
        m4=M4Budget(budget_max=500_000),
    )
    mock = AsyncMock(return_value=_MOCK_SUMMARY)
    with patch.object(chat_module._default_llm_client, "complete_async", mock):
        response = await client_async.post("/api/v1/chat/summary", json=_summary_payload(data))
    assert response.status_code == 200
    assert response.json()["structured"]["inferred"]["budgetTier"] == "entry"


async def test_inferred_priority_score_school_zone(client_async: AsyncClient) -> None:
    data = CollectedData(
        m1=M1PropertyNeeds(property_type="house", min_bedrooms=3),
        m2=M2Lifestyle(household_size=4, has_children=True, needs_school_zone=True),
        m4=M4Budget(budget_max=900000),
    )
    mock = AsyncMock(return_value=_MOCK_SUMMARY)
    with patch.object(chat_module._default_llm_client, "complete_async", mock):
        response = await client_async.post("/api/v1/chat/summary", json=_summary_payload(data))
    assert response.status_code == 200
    priority = response.json()["structured"]["inferred"]["priorityScore"]
    assert priority["school_zone"] == 1.0
