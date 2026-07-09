"""Service-layer result for GET /chats — one row from the chats table."""

from datetime import datetime

from models.base import PropertyAIBaseModel


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
