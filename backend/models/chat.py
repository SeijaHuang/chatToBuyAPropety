"""Request/response DTOs and routing payload for the chat API."""

from pydantic import ConfigDict, Field

from models.base import PropertyAIBaseModel
from models.conversation_state import CollectedData, ConversationStateDTO


class RoutingPayload(PropertyAIBaseModel):
    """Bundled routing context passed between conversation layers.

    Attributes:
        intent: Classified intent for this conversation turn.
        collected_data: Snapshot of all collected fields at routing time.
        session_id: Session identifier for the conversation.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "intent": "recommend_suburbs",
                "collectedData": {"m1": {}, "m2": {}, "m3": {}, "m4": {}},
                "sessionId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            }
        }
    )

    intent: str
    collected_data: CollectedData
    session_id: str


class ChatRequest(PropertyAIBaseModel):
    """Inbound payload for a single conversation turn.

    Attributes:
        message: The user's message text. Must be non-empty.
        state: The full current conversation state held by the client.
    """

    # Extends parent config with an OpenAPI example; alias_generator and
    # populate_by_name are inherited from PropertyAIBaseModel.
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "I want to buy a 3-bedroom house to live in",
                "state": {
                    "sessionId": "test-session-001",
                    "status": "IN_PROGRESS",
                    "currentModule": "M1_PROPERTY_NEEDS",
                    "completionStatus": {
                        "M1": False,
                        "M2": False,
                        "M3": False,
                        "M4": False,
                    },
                    "collectedData": {"m1": {}, "m2": {}, "m3": {}, "m4": {}},
                    "conversationHistory": [],
                },
            }
        },
    )

    message: str = Field(min_length=1)
    state: ConversationStateDTO


class ChatResponse(PropertyAIBaseModel):
    """Outbound payload returned after processing a conversation turn.

    Attributes:
        reply: The assistant's reply text.
        extracted: Business fields extracted by the LLM tool call in Round 1.
        updated_state: Conversation state after merging extracted fields and advancing modules.
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
                "updatedState": {
                    "sessionId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "status": "IN_PROGRESS",
                    "currentModule": "M2_LIFESTYLE",
                    "completionStatus": {"M1": True, "M2": False, "M3": False, "M4": False},
                    "collectedData": {
                        "m1": {
                            "propertyType": "house",
                            "minBedrooms": 3,
                            "intendedUse": "owner_occupier",
                        },
                        "m2": {},
                        "m3": {},
                        "m4": {},
                    },
                    "conversationHistory": [],
                },
                "routing": None,
            }
        }
    )

    reply: str
    extracted: dict[str, object]
    updated_state: ConversationStateDTO
    routing: RoutingPayload | None = None
