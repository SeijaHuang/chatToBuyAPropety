"""Response DTO for POST /chat."""

from pydantic import ConfigDict

from models.base import PropertyAIBaseModel
from models.shared.conversation_snapshot import ConversationSnapshotDTO
from models.shared.routing import RoutingPayload


class ChatResponse(PropertyAIBaseModel):
    """Outbound payload returned after processing a conversation turn.

    Attributes:
        reply: The assistant's reply text.
        extracted: Business fields extracted by the LLM tool call in Round 1.
        session_id: Current session ID — either echoed back or newly generated.
        state: Lightweight snapshot of conversation state (excludes conversation_history).
        routing: Populated when the state is complete or a routing keyword is detected.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reply": "Great! To help narrow things down, how many people will be living in the property?",
                "extracted": {
                    "property_type": "house",
                    "min_bedrooms": 3,
                    "intended_use": "owner_occupier",
                },
                "sessionId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "state": {
                    "sessionId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "currentModule": "M1_PROPERTY_NEEDS",
                    "status": "IN_PROGRESS",
                },
                "routing": None,
            }
        }
    )

    reply: str
    extracted: dict[str, object]
    session_id: str
    state: ConversationSnapshotDTO
    routing: RoutingPayload | None = None
