"""Request/response DTOs and routing payload for the chat API."""

from datetime import datetime
from enum import StrEnum

from pydantic import ConfigDict, Field

from models.base import PropertyAIBaseModel
from models.conversation_state import (
    CollectedData,
    CompletionStatus,
    EModule,
    EStatus,
    EUserIntent,
)
from models.financial import BorrowingCapacityResult, BudgetGapResult
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


class ConversationSnapshotDTO(PropertyAIBaseModel):
    """Lightweight conversation state snapshot returned in ChatResponse.

    Mirrors ConversationStateDTO but omits conversation_history to keep
    the HTTP payload small. Frontend uses this as a read-only display cache.

    Attributes:
        session_id: UUID v4 session identifier.
        current_module: The module currently being collected.
        status: Overall session status.
        completion_status: Per-module completion flags.
        collected_data: All collected fields across M1–M4.
        borrowing_capacity: Borrowing capacity estimate; populated after M4 salary is collected.
        budget_gap: Budget gap result; populated when budget_max and suburb data are available.
    """

    session_id: str
    current_module: EModule
    status: EStatus
    completion_status: CompletionStatus
    collected_data: CollectedData
    borrowing_capacity: BorrowingCapacityResult | None = None
    budget_gap: BudgetGapResult | None = None


class ChatSessionDTO(PropertyAIBaseModel):
    """Metadata for a single chat session — one row from the chats table.

    Returned as items in the GET /chats list endpoint. Contains only session-level
    fields, not the full conversation history or collected data details.

    Attributes:
        session_id: UUID v4 session identifier.
        status: Current session status (IN_PROGRESS or REQUIREMENTS_COMPLETE).
        initial_intent: Intent classified at M1 completion; None while M1 is incomplete.
        created_at: Timestamp when the session was first persisted.
        updated_at: Timestamp of the most recent upsert.
        completed_at: Timestamp when all four modules were completed; None if in progress.
    """

    session_id: str
    status: str
    initial_intent: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class ChatRequest(PropertyAIBaseModel):
    """Inbound payload for a single conversation turn.

    Attributes:
        session_id: UUID v4 session identifier. When None (first message), the backend
            generates a new UUID v4 and returns it in ChatResponse.session_id.
        message: The user's message text. Must be non-empty.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sessionId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "message": "I want to buy a 3-bedroom house to live in",
            }
        },
    )

    session_id: str | None = None
    message: str = Field(min_length=1)


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
