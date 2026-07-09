"""Request DTO for POST /chat."""

from pydantic import ConfigDict, Field

from models.base import PropertyAIBaseModel


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
