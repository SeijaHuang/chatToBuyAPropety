"""Routing payload passed from Part 1 to Part 2 (PRD §16.3)."""

from datetime import datetime
from enum import StrEnum

from pydantic import ConfigDict

from models.base import PropertyAIBaseModel
from models.shared.enums import EUserIntent
from models.shared.user_needs import UserNeeds


class EExecutionMode(StrEnum):
    """Downstream execution mode for Part 2 routing."""

    CODE_DRIVEN = "code_driven"  # known intent — direct agent dispatch
    AGENTIC_LOOP = "agentic_loop"  # open-ended — LLM orchestrates agents


class ETriggerSource(StrEnum):
    """What caused the routing payload to be emitted."""

    AUTO_COMPLETE = "auto_complete"
    KEYWORD = "keyword"
    MANUAL = "manual"


class RoutingPayload(PropertyAIBaseModel):
    """Bundled routing context passed to Part 2 (PRD §16.3).

    Attributes:
        intent: Classified intent for this conversation turn.
        session_id: Session identifier for the conversation.
        user_needs: Full Part 1 output snapshot.
        execution_mode: code_driven = direct agent dispatch, agentic_loop = LLM orchestrates.
        agents_hint: Suggested agents for Mode A execution.
        triggered_at: Timestamp when routing was triggered.
        trigger_source: What caused the routing trigger.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "intent": "recommend_suburbs",
                "sessionId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "executionMode": "code_driven",
                "agentsHint": ["suburb_agent", "price_agent"],
                "triggeredAt": "2026-05-19T00:00:00Z",
                "triggerSource": "auto_complete",
            }
        }
    )

    intent: EUserIntent
    session_id: str
    user_needs: UserNeeds
    execution_mode: EExecutionMode
    agents_hint: list[str]
    triggered_at: datetime
    trigger_source: ETriggerSource
