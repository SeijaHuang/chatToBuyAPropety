"""Constructs LLM system prompts for each conversation module — the sole source of prompt strings."""

from conversation.state_machine import MODULE_COMPLETION_RULES
from models.schemas import CollectedData, CompletionStatus, ConversationStateDTO, EModule

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

    if state.completion_status.m1:
        intended_use = state.collected_data.m1.intended_use
        if intended_use == "investment":
            sections.append(_INVESTMENT_CONTEXT)
        else:
            sections.append(_OWNER_OCCUPIER_CONTEXT)

    sections.append(_GUARDRAIL_RULES)

    return "\n\n".join(sections)
