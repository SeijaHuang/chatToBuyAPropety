"""Output contract models for Part 1 → Part 2 handoff (PRD §12)."""

from datetime import datetime

from models.base import PropertyAIBaseModel
from models.conversation_state import CollectedData, EUserIntent


class UserNeeds(PropertyAIBaseModel):
    """Full Part 1 output snapshot passed to downstream Part 2 agents."""

    session_id: str
    generated_at: datetime
    schema_version: str = "1.1"
    collected: CollectedData
    initial_intent: EUserIntent
