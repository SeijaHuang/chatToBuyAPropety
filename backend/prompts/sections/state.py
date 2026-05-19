"""Dynamic state section builders for conversation progress and collected field summaries."""

from conversation.state_machine import MODULE_COMPLETION_RULES, ModuleRequirements
from models.conversation_state import (
    CollectedData,
    CompletionStatus,
    ConversationStateDTO,
    EModule,
    TSubmodel,
)


def build_completed_list(completion: CompletionStatus) -> str:
    """Return a comma-separated list of completed module names, or 'none'.

    Args:
        completion: Current per-module completion flags.

    Returns:
        Comma-separated completed module names, or the string 'none'.
    """
    completed: list[str] = [
        module.value
        for module, rules in MODULE_COMPLETION_RULES.items()
        if completion[rules.submodel_attr]
    ]
    return ", ".join(completed) if completed else "none"


def build_collected_summary(data: CollectedData) -> str:
    """Return a comma-separated list of non-None field values across all modules, or 'none'.

    Args:
        data: The accumulated conversation data.

    Returns:
        Comma-separated 'submodel.field: value' entries, or the string 'none'.
    """
    pairs: list[str] = []
    for _module, rules in MODULE_COMPLETION_RULES.items():
        sub: TSubmodel = data[rules.submodel_attr]
        for field, value in sub.model_dump().items():
            if value is not None:
                pairs.append(f"{rules.submodel_attr}.{field}: {value}")
    return ", ".join(pairs) if pairs else "none"


def build_missing_fields(module: EModule, data: CollectedData) -> str:
    """Return a comma-separated list of required fields still missing for the given module.

    Args:
        module: The module to evaluate.
        data: The accumulated conversation data.

    Returns:
        Comma-separated missing required field names, or the string 'none'.
    """
    rules: ModuleRequirements | None = MODULE_COMPLETION_RULES.get(module)
    if rules is None:
        return "none"
    sub: TSubmodel = data[rules.submodel_attr]
    dumped: dict[str, object] = sub.model_dump()
    required: frozenset[str] = rules.required_fields | rules.extra_required(data)
    missing: list[str] = [f for f in required if dumped.get(f) is None]
    return ", ".join(missing) if missing else "none"


def build_state_section(state: ConversationStateDTO) -> str:
    """Return the formatted current-state section for injection into prompts.

    Args:
        state: The current conversation state.

    Returns:
        Multi-line string showing active module, completed modules, collected
        fields, and missing required fields.
    """
    return (
        f"Current module: {state.current_module.value}\n"
        f"Completed modules: {build_completed_list(state.completion_status)}\n"
        f"Already collected: {build_collected_summary(state.collected_data)}\n"
        f"Missing required fields: {build_missing_fields(state.current_module, state.collected_data)}"
    )
