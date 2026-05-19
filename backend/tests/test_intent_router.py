"""Tests for conversation/intent_router.py — Story S-E."""

from conversation.intent_router import classify_intent
from domain.user_needs_builder import build_user_needs
from models.conversation_state import CompletionStatus, ConversationStateDTO
from models.user_needs import UserNeeds


def _incomplete_state(session_id: str = "test-session-001") -> ConversationStateDTO:
    return ConversationStateDTO(session_id=session_id)


def _complete_state(session_id: str = "test-session-001") -> ConversationStateDTO:
    return ConversationStateDTO(
        session_id=session_id,
        completion_status=CompletionStatus(M1=True, M2=True, M3=True, M4=True),
    )


def _needs(state: ConversationStateDTO) -> UserNeeds:
    return build_user_needs(state.collected_data, state.session_id)


def test_returns_none_when_incomplete_and_no_trigger() -> None:
    """SE-1: returns None when incomplete and no keyword."""
    state = _incomplete_state()
    result = classify_intent("Tell me more about myself", state, _needs(state))
    assert result is None


def test_returns_payload_when_all_complete() -> None:
    """SE-2: returns a RoutingPayload (not None) when all modules are complete."""
    state = _complete_state()
    result = classify_intent("What do you think?", state, _needs(state))
    assert result is not None


def test_recommend_intent_on_keyword_match() -> None:
    """SE-3: 'suburb' keyword maps to recommend_suburbs intent."""
    state = _incomplete_state()
    result = classify_intent("Which suburb should I look at?", state, _needs(state))
    assert result is not None and result.intent == "recommend_suburbs"


def test_property_detail_intent_on_address_match() -> None:
    """SE-4: a street address maps to property_detail intent."""
    state = _incomplete_state()
    result = classify_intent("12 Smith Street 3000", state, _needs(state))
    assert result is not None and result.intent == "property_detail"


def test_property_detail_intent_on_property_id_match() -> None:
    """SE-4b: a property ID keyword maps to property_detail intent."""
    state = _incomplete_state()
    result = classify_intent("Tell me about property_id 98765", state, _needs(state))
    assert result is not None and result.intent == "property_detail"


def test_pure_number_does_not_trigger_property_detail() -> None:
    """SE-4c: a plain dollar amount without a street keyword does not trigger property_detail."""
    state = _incomplete_state()
    result = classify_intent("my budget is $8000", state, _needs(state))
    assert result is None


def test_open_ended_query_as_fallback_when_complete() -> None:
    """SE-5: fallback intent is open_ended_query when all complete and no keyword matched."""
    state = _complete_state()
    result = classify_intent("What are my options?", state, _needs(state))
    assert result is not None and result.intent == "open_ended_query"


def test_routing_payload_contains_correct_collected_data() -> None:
    """SE-6: RoutingPayload.user_needs.collected matches the state's collected_data."""
    state = _complete_state()
    result = classify_intent("What next?", state, _needs(state))
    assert result is not None and result.user_needs.collected == state.collected_data


def test_routing_payload_contains_correct_session_id() -> None:
    """SE-7: RoutingPayload.session_id matches the state's session_id."""
    state = ConversationStateDTO(
        session_id="unique-session-xyz",
        completion_status=CompletionStatus(M1=True, M2=True, M3=True, M4=True),
    )
    result = classify_intent("Show me something", state, _needs(state))
    assert result is not None and result.session_id == "unique-session-xyz"


def test_execution_mode_code_driven_for_recommend_suburbs() -> None:
    """PRD §16.4: recommend_suburbs uses code_driven mode with suburb_agent and price_agent."""
    state = _incomplete_state()
    result = classify_intent("Which suburb should I look at?", state, _needs(state))
    assert result is not None
    assert result.execution_mode == "code_driven"
    assert "suburb_agent" in result.agents_hint
    assert "price_agent" in result.agents_hint


def test_execution_mode_agentic_loop_for_open_ended_query() -> None:
    """PRD §16.4: open_ended_query uses agentic_loop mode with empty agents_hint."""
    state = _complete_state()
    result = classify_intent("What are my options?", state, _needs(state))
    assert result is not None
    assert result.execution_mode == "agentic_loop"
    assert result.agents_hint == []


def test_trigger_source_keyword_when_keyword_matched() -> None:
    """trigger_source is 'keyword' when an intent keyword triggered routing."""
    state = _incomplete_state()
    result = classify_intent("find me a property", state, _needs(state))
    assert result is not None and result.trigger_source == "keyword"


def test_trigger_source_auto_complete_when_all_modules_done() -> None:
    """trigger_source is 'auto_complete' when all modules are complete."""
    state = _complete_state()
    result = classify_intent("What are my options?", state, _needs(state))
    assert result is not None and result.trigger_source == "auto_complete"
