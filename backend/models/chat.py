"""Request/response DTOs and routing payload for the chat API."""

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from models.conversation_state import CollectedData, ConversationStateDTO


class RoutingPayload(BaseModel):
    """Bundled routing context passed between conversation layers."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    intent: str
    collected_data: CollectedData
    session_id: str


class ChatRequest(BaseModel):
    """Inbound payload for a single conversation turn.

    Attributes:
        message: The user's message text. Must be non-empty.
        state: The full current conversation state held by the client.
    """

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
        }
    )

    message: str = Field(min_length=1)
    state: ConversationStateDTO


class ChatResponse(BaseModel):
    """Outbound payload returned after processing a conversation turn.

    Attributes:
        reply: The assistant's reply text.
        extracted: Business fields extracted by the LLM tool call in Round 1.
        updated_state: Conversation state after merging extracted fields and advancing modules.
        routing: Populated when the state is complete or a routing keyword is detected.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    reply: str
    extracted: dict[str, object]
    updated_state: ConversationStateDTO
    routing: RoutingPayload | None = None
