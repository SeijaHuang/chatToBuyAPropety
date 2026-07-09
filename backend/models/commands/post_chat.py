"""Service-layer command for POST /chat."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ProcessChatTurnCommand:
    """Parameters for IChatService.process_turn_async, built by the router.

    Attributes:
        session_id: Existing session UUID, or None to create a new session.
        message: The user's message text for this turn.
        anon_id: Anonymous user identity, used for the Postgres upsert.
    """

    session_id: UUID | None
    message: str
    anon_id: UUID
