"""Service-layer command for POST /chat/summary."""

from dataclasses import dataclass

from models.shared.enums import EUserIntent
from models.shared.submodels import CollectedData


@dataclass(frozen=True)
class GenerateChatSummaryCommand:
    """Parameters for IChatService.generate_summary_async, built by the router.

    Attributes:
        collected_data: Accumulated field values from the conversation.
        session_id: Session identifier for the UserNeeds handoff snapshot.
        initial_intent: Intent classified at M1 completion.
    """

    collected_data: CollectedData
    session_id: str
    initial_intent: EUserIntent
