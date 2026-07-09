"""Service-layer command for GET /chat/{session_id}."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RestoreChatSessionCommand:
    """Parameters for IChatService.restore_session_async, built by the router.

    Attributes:
        session_id: Session identifier, already validated by the caller.
    """

    session_id: UUID
