"""Builds a UserNeeds snapshot from CollectedData (PRD §12.2)."""

from datetime import UTC, datetime
from typing import Literal

from models.conversation_state import CollectedData
from models.user_needs import InferredNeeds, UserNeeds

_TInitialIntent = Literal[
    "recommend_suburbs", "list_properties", "property_detail", "open_ended_query"
]


def build_user_needs(
    collected: CollectedData,
    session_id: str,
    initial_intent: _TInitialIntent = "open_ended_query",
) -> UserNeeds:
    """Derive InferredNeeds from CollectedData and assemble a UserNeeds snapshot.

    Args:
        collected: Accumulated conversation data across all modules.
        session_id: Unique identifier for the conversation session.
        initial_intent: Routing intent classified at conversation start.

    Returns:
        Fully populated UserNeeds with inferred signals.
    """
    inferred = _infer_needs(collected)
    return UserNeeds(
        session_id=session_id,
        generated_at=datetime.now(tz=UTC),
        collected=collected,
        inferred=inferred,
        initial_intent=initial_intent,
    )


def _infer_needs(collected: CollectedData) -> InferredNeeds:
    return InferredNeeds(
        buyer_type=_buyer_type(collected),
        household_profile=_household_profile(collected),
        budget_tier=_budget_tier(collected),
        priority_score=_priority_score(collected),
    )


def _buyer_type(
    collected: CollectedData,
) -> Literal["owner_occupier", "investor", "both"]:
    intended_use = collected.m1.intended_use
    if intended_use == "investment":
        return "investor"
    if intended_use == "both":
        return "both"
    return "owner_occupier"


def _household_profile(
    collected: CollectedData,
) -> Literal["single", "couple", "family", "unknown"]:
    m2 = collected.m2
    if m2.has_children is True:
        return "family"
    if m2.household_size == 2:
        return "couple"
    if m2.household_size == 1:
        return "single"
    return "unknown"


def _budget_tier(
    collected: CollectedData,
) -> Literal["entry", "mid", "premium", "luxury"]:
    budget_max = collected.m4.budget_max
    if budget_max is None or budget_max < 700_000:
        return "entry"
    if budget_max < 1_200_000:
        return "mid"
    if budget_max < 2_000_000:
        return "premium"
    return "luxury"


def _priority_score(collected: CollectedData) -> dict[str, float]:
    m1, m2, m3, m4 = collected.m1, collected.m2, collected.m3, collected.m4

    true_features = sum(
        1 for flag in (m1.wants_pool, m1.wants_outdoor, m1.wants_study) if flag is True
    )

    return {
        "budget_sensitivity": (
            1.0 if m4.budget_max is not None and m4.budget_max < 700_000 else 0.5
        ),
        "school_zone": 1.0 if m2.needs_school_zone is True else 0.0,
        "commute_convenience": (
            1.0 if m3.commute_max_mins is not None and m3.commute_max_mins < 30 else 0.5
        ),
        "lifestyle_match": (
            1.0 if m3.lifestyle_vibe is not None and m3.lifestyle_vibe != "any" else 0.0
        ),
        "property_features": true_features / 3.0,
    }
