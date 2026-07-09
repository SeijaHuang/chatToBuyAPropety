"""Response DTO for GET /chat/{session_id}."""

from models.base import PropertyAIBaseModel
from models.shared.conversation_snapshot import ConversationSnapshotDTO


class ChatSessionRestoreResponse(PropertyAIBaseModel):
    """Response body for GET /chat/{session_id}.

    Attributes:
        resume_message: None on a Redis hit (history is returned instead); the
            LLM-generated welcome-back string when state was restored from the DB.
            Frontend renders this as the first assistant message when non-null.
        state: Lightweight conversation snapshot — same shape as ChatResponse.state.
            Used to hydrate the progress bar and collected-data panel.
        conversation_history: Full message history on a Redis hit. Empty list on a
            DB restore (history not persisted); frontend shows resume_message instead.
    """

    resume_message: str | None
    state: ConversationSnapshotDTO
    conversation_history: list[dict[str, object]]
