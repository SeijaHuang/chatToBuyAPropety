"""Assembles LLM system prompts — the sole public interface for all prompt construction.

All prompt string content lives in prompts/sections/. This module is responsible
only for composing those sections into the correct order for each prompt type.
"""

from models.conversation_state import (
    CollectedData,
    ConversationStateDTO,
    EIntendedUse,
    ESubmodel,
    ESubmodelLabel,
)
from prompts.sections.context import INVESTMENT_CONTEXT, OWNER_OCCUPIER_CONTEXT
from prompts.sections.financial import build_borrowing_capacity_section, build_budget_gap_section
from prompts.sections.guardrails import GUARDRAIL_RULES
from prompts.sections.instructions import (
    EXTRACTION_INSTRUCTION,
    QUESTION_TASK_INSTRUCTION,
    SESSION_RESTORE_INSTRUCTION,
)
from prompts.sections.role import ROLE_DEFINITION
from prompts.sections.state import build_state_section

_SUBMODEL_LABELS: dict[ESubmodel, ESubmodelLabel] = {
    ESubmodel.M1: ESubmodelLabel.M1,
    ESubmodel.M2: ESubmodelLabel.M2,
    ESubmodel.M3: ESubmodelLabel.M3,
    ESubmodel.M4: ESubmodelLabel.M4,
}


def build_extraction_prompt(state: ConversationStateDTO) -> str:
    """Build a minimal system prompt focused solely on field extraction.

    Args:
        state: The current conversation state (used to indicate active module focus).

    Returns:
        A concise system prompt string for extraction-only LLM calls.
    """
    return (
        f"You are a data extraction assistant for a property buying conversation.\n"
        f"Active module: {state.current_module.value}\n\n"
        f"{EXTRACTION_INSTRUCTION}"
    )


def build_question_prompt(state: ConversationStateDTO) -> str:
    """Build the system prompt for the Round 2 question-generation LLM call.

    Sees the state after Round 1 extraction so the generated question targets the
    freshest missing-fields reality. Assembles role definition, updated state, optional
    M1→M2 inference context, borrowing capacity estimate (when available), guardrail
    rules, and a question-task instruction.

    Args:
        state: The updated conversation state after field extraction.

    Returns:
        A fully assembled system prompt string for question-generation calls.
    """
    sections: list[str] = [ROLE_DEFINITION, build_state_section(state)]

    if state.completion_status.M1:
        intended_use: EIntendedUse | None = state.collected_data.m1.intended_use
        sections.append(
            INVESTMENT_CONTEXT if intended_use == "investment" else OWNER_OCCUPIER_CONTEXT
        )

    capacity_section = build_borrowing_capacity_section(state.borrowing_capacity)
    if capacity_section:
        sections.append(capacity_section)

    gap_section = build_budget_gap_section(state.budget_gap)
    if gap_section:
        sections.append(gap_section)

    sections.append(GUARDRAIL_RULES)
    sections.append(QUESTION_TASK_INSTRUCTION)

    return "\n\n".join(sections)


def build_system_prompt(state: ConversationStateDTO) -> str:
    """Build the dynamic system prompt for the LLM based on current conversation state.

    Assembles four ordered sections: static role definition, dynamic state injection,
    an optional M1→M2 inference context (only when M1 is complete), and static
    guardrail rules.

    Args:
        state: The current conversation state including module progress and collected data.

    Returns:
        A fully assembled system prompt string containing all applicable sections.
    """
    sections: list[str] = [ROLE_DEFINITION, build_state_section(state)]

    if state.completion_status.M1:
        intended_use: EIntendedUse | None = state.collected_data.m1.intended_use
        sections.append(
            INVESTMENT_CONTEXT if intended_use == "investment" else OWNER_OCCUPIER_CONTEXT
        )

    sections.append(GUARDRAIL_RULES)

    return "\n\n".join(sections)


def build_session_restore_prompt(state: ConversationStateDTO) -> str:
    """Build the system prompt for the LLM welcome-back message on DB restore.

    Used only by the GET /chat/{session_id} DB-fallback path. Distinct from
    build_question_prompt (ongoing turn) and build_summary_prompt (final brief)
    because the intent is to orient a returning user, not collect or summarise.

    Args:
        state: Reconstructed ConversationStateDTO from DB (conversation_history is empty).

    Returns:
        System prompt string for llm_client.complete_async().
    """
    sections: list[str] = [
        ROLE_DEFINITION,
        build_state_section(state),
        GUARDRAIL_RULES,
        SESSION_RESTORE_INSTRUCTION,
    ]
    return "\n\n".join(sections)


def build_summary_prompt(collected_data: CollectedData) -> str:
    """Build the system prompt for generating a natural-language requirements summary.

    Iterates over all four sub-models and injects only non-None field values so the
    LLM has concrete data to summarise.

    Args:
        collected_data: The fully accumulated field values from the conversation.

    Returns:
        A system prompt string ready to pass to a plain completion call.
    """
    field_lines: list[str] = []
    for submodel, label in _SUBMODEL_LABELS.items():
        sub = getattr(collected_data, submodel)
        for field, value in sub.model_dump().items():
            if value is not None:
                field_lines.append(f"  {label} — {field}: {value}")

    collected_context: str = "\n".join(field_lines) if field_lines else "  (no data collected)"

    return (
        "You are a professional property buying assistant writing a client brief.\n\n"
        "You have collected the following property requirements:\n"
        f"{collected_context}\n\n"
        "Write a natural-language summary of these requirements in English. "
        "Use flowing paragraphs (not bullet lists). "
        "Cover all four dimensions where data is available: budget, property type, "
        "location and commute, and lifestyle. "
        "Only mention fields that have a value — do not speculate about missing information."
    )
