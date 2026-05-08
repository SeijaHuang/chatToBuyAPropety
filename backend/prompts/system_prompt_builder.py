"""Constructs LLM system prompts for each conversation module — the sole source of prompt strings."""

from conversation.state_machine import MODULE_COMPLETION_RULES
from models.schemas import (
    CollectedData,
    CompletionStatus,
    ConversationStateDTO,
    EModule,
    ESubmodel,
    ESubmodelLabel,
)

_SUBMODEL_LABELS: dict[ESubmodel, ESubmodelLabel] = {
    ESubmodel.M1: ESubmodelLabel.M1,
    ESubmodel.M2: ESubmodelLabel.M2,
    ESubmodel.M3: ESubmodelLabel.M3,
    ESubmodel.M4: ESubmodelLabel.M4,
}

_ROLE_DEFINITION = """\
You are an AI property buying assistant for the Australian market.
Your role is to collect buyer requirements through natural conversation.
You are NOT a licensed buyer's agent, financial advisor, or legal professional."""

_GUARDRAIL_RULES = """\
Rule 1 — Property recommendations: present data only, never give a direct recommendation
Rule 2 — Market information: provide data, always follow with a question returning focus to user needs
Rule 3 — Budget shortfall: flag the gap directly and kindly, suggest alternatives
Rule 4 — Legal/compliance: explain concepts, refer to solicitor or conveyancer
Rule 5 — Investment predictions: historical data only, always append ASIC disclaimer
Rule 6 — Role identity: transparent explanation of AI assistant boundaries"""

_OWNER_OCCUPIER_CONTEXT = """\
Context: The buyer is an owner-occupier. Focus on family structure, school zone needs,
and lifestyle fit when asking about module 2 requirements."""

_INVESTMENT_CONTEXT = """\
Context: The buyer is an investor. Focus on tenant profile, rental yield priority,
and property management considerations when asking about module 2 requirements."""

_EXTRACTION_INSTRUCTION = (
    "Extract only the property requirement fields explicitly stated in the user's message. "
    "Do not infer or guess missing values. Populate only fields that are clearly mentioned."
)

_QUESTION_TASK_INSTRUCTION = (
    "Task: Generate exactly ONE short, natural, conversational question targeting the most "
    "important missing required field for the current module. "
    "Do not re-ask fields already collected."
)


def _build_completed_list(completion: CompletionStatus) -> str:
    """Return a comma-separated list of completed module names, or 'none'."""
    completed = [
        module.value
        for module, rules in MODULE_COMPLETION_RULES.items()
        if completion[rules.submodel_attr]
    ]
    return ", ".join(completed) if completed else "none"


def _build_collected_summary(data: CollectedData) -> str:
    """Return a comma-separated list of non-None field values across all modules, or 'none'."""
    pairs: list[str] = []
    for module, rules in MODULE_COMPLETION_RULES.items():
        sub = data[rules.submodel_attr]
        for field, value in sub.model_dump().items():
            if value is not None:
                pairs.append(f"{rules.submodel_attr}.{field}: {value}")
    return ", ".join(pairs) if pairs else "none"


def _build_missing_fields(module: EModule, data: CollectedData) -> str:
    """Return a comma-separated list of required fields still missing for the given module."""
    rules = MODULE_COMPLETION_RULES.get(module)
    if rules is None:
        return "none"
    sub = data[rules.submodel_attr]
    dumped = sub.model_dump()
    required = rules.required_fields | rules.extra_required(data)
    missing = [f for f in required if dumped.get(f) is None]
    return ", ".join(missing) if missing else "none"


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
        f"{_EXTRACTION_INSTRUCTION}"
    )


def build_question_prompt(state: ConversationStateDTO) -> str:
    """Build the system prompt for the Round 2 question-generation LLM call.

    Sees the state after Round 1 extraction so the generated question targets the
    freshest missing-fields reality. Assembles role definition, updated state, optional
    M1→M2 inference context, guardrail rules, and a question-task instruction.

    Args:
        state: The updated conversation state after field extraction.

    Returns:
        A fully assembled system prompt string for question-generation calls.
    """
    sections: list[str] = [_ROLE_DEFINITION]

    state_section = (
        f"Current module: {state.current_module.value}\n"
        f"Completed modules: {_build_completed_list(state.completion_status)}\n"
        f"Already collected: {_build_collected_summary(state.collected_data)}\n"
        f"Missing required fields: {_build_missing_fields(state.current_module, state.collected_data)}"
    )
    sections.append(state_section)

    if state.completion_status.M1:
        intended_use = state.collected_data.m1.intended_use
        if intended_use == "investment":
            sections.append(_INVESTMENT_CONTEXT)
        else:
            sections.append(_OWNER_OCCUPIER_CONTEXT)

    sections.append(_GUARDRAIL_RULES)
    sections.append(_QUESTION_TASK_INSTRUCTION)

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
    sections: list[str] = [_ROLE_DEFINITION]

    state_section = (
        f"Current module: {state.current_module.value}\n"
        f"Completed modules: {_build_completed_list(state.completion_status)}\n"
        f"Already collected: {_build_collected_summary(state.collected_data)}\n"
        f"Missing required fields: {_build_missing_fields(state.current_module, state.collected_data)}"
    )
    sections.append(state_section)

    if state.completion_status.M1:
        intended_use = state.collected_data.m1.intended_use
        if intended_use == "investment":
            sections.append(_INVESTMENT_CONTEXT)
        else:
            sections.append(_OWNER_OCCUPIER_CONTEXT)

    sections.append(_GUARDRAIL_RULES)

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

    collected_context = "\n".join(field_lines) if field_lines else "  (no data collected)"

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
