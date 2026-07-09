"""Service-layer result for GET /chat/{session_id}."""

from dataclasses import dataclass

from models.shared.conversation_state import ConversationStateDTO


@dataclass(frozen=True)
class ChatSessionRestoreDTO:
    """Outcome of resolving GET /chat/{session_id}.

    Attributes:
        resume_message: None on a Redis hit; the LLM-generated welcome-back string
            on a Postgres-fallback restore.
        state: Resolved conversation state — the live Redis copy, or the
            reconstructed Postgres snapshot with completion_status/current_module
            re-derived (neither is persisted, so both must be recomputed).
        conversation_history: Full history on a Redis hit; empty on a Postgres
            restore, since raw history is never persisted to Postgres.
    """

    resume_message: str | None
    state: ConversationStateDTO
    conversation_history: list[dict[str, object]]
