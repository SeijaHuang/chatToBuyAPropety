"""Output contract models for Part 1 → Part 2 handoff (PRD §12)."""

from datetime import datetime
from typing import Literal

from models.base import PropertyAIBaseModel
from models.conversation_state import CollectedData


class InferredNeeds(PropertyAIBaseModel):
    """Derived property-search signals computed from CollectedData."""

    buyer_type: Literal["owner_occupier", "investor", "both"]
    household_profile: Literal["single", "couple", "family", "unknown"]
    budget_tier: Literal["entry", "mid", "premium", "luxury"]
    borrowing_capacity: int | None = None
    commute_polygon: list[object] | None = None
    priority_score: dict[str, float]


class UserNeeds(PropertyAIBaseModel):
    """Full Part 1 output snapshot passed to downstream Part 2 agents."""

    session_id: str
    generated_at: datetime
    schema_version: str = "1.1"
    collected: CollectedData
    inferred: InferredNeeds
    initial_intent: Literal[
        "recommend_suburbs", "list_properties", "property_detail", "open_ended_query"
    ]
