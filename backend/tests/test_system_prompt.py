"""Tests for prompts/system_prompt_builder.py — Story S-C."""

from models.conversation_state import (
    CollectedData,
    CompletionStatus,
    ConversationStateDTO,
    EModule,
    EStatus,
    M1PropertyNeeds,
)
from prompts.system_prompt_builder import (
    build_extraction_prompt,
    build_question_prompt,
    build_system_prompt,
)


def _make_state(
    current_module: EModule = EModule.M1_PROPERTY_NEEDS,
    completion_status: CompletionStatus | None = None,
    collected_data: CollectedData | None = None,
) -> ConversationStateDTO:
    return ConversationStateDTO(
        session_id="test-session",
        status=EStatus.IN_PROGRESS,
        current_module=current_module,
        completion_status=completion_status
        if completion_status is not None
        else CompletionStatus(),
        collected_data=collected_data if collected_data is not None else CollectedData(),
    )


def test_output_contains_role_definition() -> None:
    """SC-1: Output begins with the static role definition block."""
    result = build_system_prompt(_make_state())
    assert "You are an AI property buying assistant for the Australian market." in result
    assert (
        "You are NOT a licensed buyer's agent, financial advisor, or legal professional." in result
    )


def test_output_contains_current_module() -> None:
    """SC-2: current_module in Section 2 reflects the active module."""
    result = build_system_prompt(_make_state(current_module=EModule.M2_LIFESTYLE))
    assert "M2_LIFESTYLE" in result


def test_collected_summary_excludes_none_fields() -> None:
    """SC-3: collected_summary lists non-None fields and omits fields that are still None."""
    data = CollectedData(m1=M1PropertyNeeds(property_type="house"))
    result = build_system_prompt(_make_state(collected_data=data))
    assert "m1.property_type: house" in result
    # None fields must not appear in the "Already collected" summary (prefixed form)
    assert "m1.min_bedrooms" not in result


def test_section_3_absent_when_m1_incomplete() -> None:
    """SC-4: Section 3 (inference context) is not injected when M1 is still incomplete."""
    result = build_system_prompt(_make_state())
    assert "tenant profile" not in result
    assert "school zone" not in result
    assert "owner-occupier" not in result
    assert "investor" not in result


def test_section_3_contains_tenant_guidance_for_investment() -> None:
    """SC-5: When M1 complete and intended_use is 'investment', Section 3 focuses on tenant."""
    data = CollectedData(
        m1=M1PropertyNeeds(property_type="unit", min_bedrooms=2, intended_use="investment")
    )
    state = _make_state(
        current_module=EModule.M2_LIFESTYLE,
        completion_status=CompletionStatus(M1=True),
        collected_data=data,
    )
    result = build_system_prompt(state)
    assert "tenant profile" in result


def test_section_3_contains_school_guidance_for_owner_occupier() -> None:
    """SC-6: When M1 complete and intended_use is 'owner_occupier', Section 3 mentions school zone."""
    data = CollectedData(
        m1=M1PropertyNeeds(property_type="house", min_bedrooms=3, intended_use="owner_occupier")
    )
    state = _make_state(
        current_module=EModule.M2_LIFESTYLE,
        completion_status=CompletionStatus(M1=True),
        collected_data=data,
    )
    result = build_system_prompt(state)
    assert "school zone" in result


def test_all_six_guardrail_rules_present() -> None:
    """SC-7: Section 4 contains all six guardrail rule entries."""
    result = build_system_prompt(_make_state())
    for rule_number in range(1, 7):
        assert f"Rule {rule_number}" in result


def test_output_is_nonempty_string() -> None:
    """SC-8: build_system_prompt returns a non-empty string without raising."""
    result = build_system_prompt(_make_state())
    assert isinstance(result, str)
    assert len(result) > 0


# --- build_extraction_prompt ---


def test_extraction_prompt_contains_active_module() -> None:
    """SC-9: build_extraction_prompt includes the active module identifier."""
    result = build_extraction_prompt(_make_state(current_module=EModule.M2_LIFESTYLE))
    assert "M2_LIFESTYLE" in result


def test_extraction_prompt_excludes_question_instruction() -> None:
    """SC-10: build_extraction_prompt does not contain question-generation instruction."""
    result = build_extraction_prompt(_make_state())
    assert "Generate" not in result
    assert "question" not in result.lower()


def test_extraction_prompt_is_nonempty_string() -> None:
    """SC-11: build_extraction_prompt returns a non-empty string without raising."""
    result = build_extraction_prompt(_make_state())
    assert isinstance(result, str)
    assert len(result) > 0


# --- build_question_prompt ---


def test_question_prompt_contains_role_definition() -> None:
    """SC-12: build_question_prompt includes the role definition."""
    result = build_question_prompt(_make_state())
    assert "You are an AI property buying assistant for the Australian market." in result


def test_question_prompt_contains_missing_fields() -> None:
    """SC-13: build_question_prompt lists missing required fields for the current module."""
    result = build_question_prompt(_make_state(current_module=EModule.M1_PROPERTY_NEEDS))
    assert "Missing required fields" in result
    assert "property_type" in result


def test_question_prompt_contains_task_instruction() -> None:
    """SC-14: build_question_prompt includes the one-question task instruction."""
    result = build_question_prompt(_make_state())
    assert "Generate exactly ONE" in result


def test_question_prompt_guardrail_rules_present() -> None:
    """SC-15: build_question_prompt contains all six guardrail rules."""
    result = build_question_prompt(_make_state())
    for rule_number in range(1, 7):
        assert f"Rule {rule_number}" in result


def test_question_prompt_is_nonempty_string() -> None:
    """SC-16: build_question_prompt returns a non-empty string without raising."""
    result = build_question_prompt(_make_state())
    assert isinstance(result, str)
    assert len(result) > 0
