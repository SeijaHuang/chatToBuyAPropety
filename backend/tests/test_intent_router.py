"""Tests for conversation/intent_router.py — Story S-E."""

from conversation.intent_router import classify_intent
from models.conversation_state import CompletionStatus, ConversationStateDTO


def _incomplete_state(session_id: str = "test-session-001") -> ConversationStateDTO:
    return ConversationStateDTO(session_id=session_id)


def _complete_state(session_id: str = "test-session-001") -> ConversationStateDTO:
    return ConversationStateDTO(
        session_id=session_id,
        completion_status=CompletionStatus(M1=True, M2=True, M3=True, M4=True),
    )


def test_returns_none_when_incomplete_and_no_trigger() -> None:
    """SE-1: returns None when incomplete and no keyword."""
    result = classify_intent("Tell me more about myself", _incomplete_state())
    assert result is None


def test_returns_payload_when_all_complete() -> None:
    """SE-2: returns a RoutingPayload (not None) when all modules are complete."""
    result = classify_intent("What do you think?", _complete_state())
    assert result is not None


def test_recommend_intent_on_keyword_match() -> None:
    """SE-3: 'suburb' keyword maps to recommend_suburbs intent."""
    result = classify_intent("Which suburb should I look at?", _incomplete_state())
    assert result is not None and result.intent == "recommend_suburbs"


def test_property_detail_intent_on_address_match() -> None:
    """SE-4: a street address maps to property_detail intent."""
    result = classify_intent("12 Smith Street 3000", _incomplete_state())
    assert result is not None and result.intent == "property_detail"


def test_property_detail_intent_on_property_id_match() -> None:
    """SE-4b: a property ID keyword maps to property_detail intent."""
    result = classify_intent("Tell me about property_id 98765", _incomplete_state())
    assert result is not None and result.intent == "property_detail"


def test_pure_number_does_not_trigger_property_detail() -> None:
    """SE-4c: a plain dollar amount without a street keyword does not trigger property_detail."""
    result = classify_intent("my budget is $8000", _incomplete_state())
    assert result is None


def test_open_ended_query_as_fallback_when_complete() -> None:
    """SE-5: fallback intent is open_ended_query when all complete and no keyword matched."""
    result = classify_intent("What are my options?", _complete_state())
    assert result is not None and result.intent == "open_ended_query"


def test_routing_payload_contains_correct_collected_data() -> None:
    """SE-6: RoutingPayload.collected_data matches the state's collected_data."""
    state = _complete_state()
    result = classify_intent("What next?", state)
    assert result is not None and result.collected_data is state.collected_data


def test_routing_payload_contains_correct_session_id() -> None:
    """SE-7: RoutingPayload.session_id matches the state's session_id."""
    state = ConversationStateDTO(
        session_id="unique-session-xyz",
        completion_status=CompletionStatus(M1=True, M2=True, M3=True, M4=True),
    )
    result = classify_intent("Show me something", state)
    assert result is not None and result.session_id == "unique-session-xyz"
