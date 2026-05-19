"""Request/response DTOs and routing payload for the chat API."""

from datetime import datetime
from enum import StrEnum

from pydantic import ConfigDict, Field

from models.base import PropertyAIBaseModel
from models.conversation_state import ConversationStateDTO, EUserIntent
from models.user_needs import UserNeeds


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
