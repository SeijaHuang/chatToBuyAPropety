"""Module progression logic — manages transitions between conversation modules and collected state."""

from collections.abc import Callable
from dataclasses import dataclass

from models.conversation_state import (
    CollectedData,
    CompletionStatus,
    ConversationStateDTO,
    EModule,
    EStatus,
    ESubmodel,
)

_CONTROL_KEYS: frozenset[str] = frozenset({"module_complete", "next_question", "user_intent"})


def _no_extra_required(_: CollectedData) -> frozenset[str]:
    return frozenset()


def _m2_extra_required(data: CollectedData) -> frozenset[str]:
    if data.m1.intended_use == "investment":
        return frozenset({"target_tenant"})
    return frozenset()


@dataclass(frozen=True)
class ModuleRequirements:
    """Completion and field-routing rules for a single conversation module.

    Attributes:
        submodel_attr: Attribute name on CollectedData that owns this module's fields.
        all_fields: Every field that belongs to this module, used for routing incoming values.
        required_fields: Subset of all_fields that must be non-None for the module to be complete.
        extra_required: Returns additional required fields derived from cross-module state.
    """

    submodel_attr: ESubmodel
    all_fields: frozenset[str]
    required_fields: frozenset[str]
    extra_required: Callable[[CollectedData], frozenset[str]]


MODULE_COMPLETION_RULES: dict[EModule, ModuleRequirements] = {
    EModule.M1_PROPERTY_NEEDS: ModuleRequirements(
        submodel_attr=ESubmodel.M1,
        all_fields=frozenset(
            {
                "property_type",
                "min_bedrooms",
                "max_bedrooms",
                "min_bathrooms",
                "min_carspaces",
                "min_land_size",
                "max_land_size",
                "wants_pool",
                "wants_outdoor",
                "wants_study",
                "intended_use",
            }
        ),
        required_fields=frozenset({"property_type", "min_bedrooms", "intended_use"}),
        extra_required=_no_extra_required,
    ),
    EModule.M2_LIFESTYLE: ModuleRequirements(
        submodel_attr=ESubmodel.M2,
        all_fields=frozenset(
            {
                "household_size",
                "has_children",
                "needs_school_zone",
                "has_pets",
                "work_from_home",
                "target_tenant",
            }
        ),
        required_fields=frozenset({"household_size", "has_children"}),
        extra_required=_m2_extra_required,
    ),
    EModule.M3_SUBURB_PREFERENCE: ModuleRequirements(
        submodel_attr=ESubmodel.M3,
        all_fields=frozenset(
            {
                "commute_destination",
                "commute_max_mins",
                "commute_mode",
                "preferred_suburbs",
                "excluded_suburbs",
                "lifestyle_vibe",
            }
        ),
        required_fields=frozenset({"commute_destination", "commute_max_mins"}),
        extra_required=_no_extra_required,
    ),
    EModule.M4_BUDGET: ModuleRequirements(
        submodel_attr=ESubmodel.M4,
        all_fields=frozenset(
            {
                "budget_min",
                "budget_max",
                "deposit_amount",
                "pre_tax_salary",
                "partner_salary",
                "is_joint",
                "first_home_buyer",
            }
        ),
        required_fields=frozenset({"budget_max"}),
        extra_required=_no_extra_required,
    ),
}


def is_module_complete(module: EModule, data: CollectedData) -> bool:
    """Check whether all required fields for the given module have been collected.

    Args:
        module: The module to evaluate.
        data: The accumulated conversation data.

    Returns:
        True if all required fields are non-None, False otherwise.
        Always returns False for EModule.COMPLETE.
    """
    rules = MODULE_COMPLETION_RULES.get(module)
    if rules is None:
        return False
    sub = data[rules.submodel_attr]
    all_required = rules.required_fields | rules.extra_required(data)
    return all(getattr(sub, f) is not None for f in all_required)


def get_current_module(completion: CompletionStatus) -> EModule:
    """Return the first incomplete module in M1 → M2 → M3 → M4 order.

    Args:
        completion: Current per-module completion flags.

    Returns:
        The first module that has not yet been completed, or EModule.COMPLETE
        if all four modules are done.
    """
    return completion.current_module


def recalculate_completion(data: CollectedData) -> CompletionStatus:
    """Derive a fresh CompletionStatus from the current collected data.

    Args:
        data: The accumulated conversation data.

    Returns:
        A new CompletionStatus reflecting current field coverage.
    """
    return CompletionStatus(
        M1=is_module_complete(EModule.M1_PROPERTY_NEEDS, data),
        M2=is_module_complete(EModule.M2_LIFESTYLE, data),
        M3=is_module_complete(EModule.M3_SUBURB_PREFERENCE, data),
        M4=is_module_complete(EModule.M4_BUDGET, data),
    )


def merge_extracted_fields(
    state: ConversationStateDTO, incoming: dict[str, object]
) -> ConversationStateDTO:
    """Merge LLM-extracted fields into state, then advance module if appropriate.

    Unknown keys are silently ignored. Null-safety: a non-None existing value
    is never overwritten by None from the incoming dict.

    Args:
        state: Current conversation state to mutate.
        incoming: Raw field dict from the extraction tool call response.

    Returns:
        The mutated state with updated collected data, completion status, and
        current module.
    """
    for key, value in incoming.items():
        if key in _CONTROL_KEYS or value is None:
            continue
        for rules in MODULE_COMPLETION_RULES.values():
            if key in rules.all_fields:
                setattr(state.collected_data[rules.submodel_attr], key, value)
                break

    state.completion_status = recalculate_completion(state.collected_data)
    state.current_module = get_current_module(state.completion_status)

    if state.completion_status.all_complete:
        state.status = EStatus.REQUIREMENTS_COMPLETE

    return state


async def load_state_async(session_id: str) -> ConversationStateDTO:
    """Load conversation state from Redis. Not implemented in P0.

    Args:
        session_id: The unique session identifier.

    Returns:
        The deserialised ConversationStateDTO for the session.

    Raises:
        NotImplementedError: Always — Redis persistence is a P1 feature.
    """
    raise NotImplementedError("Redis persistence is a P1 feature.")


async def save_state_async(state: ConversationStateDTO) -> None:
    """Persist conversation state to Redis. Not implemented in P0.

    Args:
        state: The conversation state to serialise and store.

    Raises:
        NotImplementedError: Always — Redis persistence is a P1 feature.
    """
    raise NotImplementedError("Redis persistence is a P1 feature.")
