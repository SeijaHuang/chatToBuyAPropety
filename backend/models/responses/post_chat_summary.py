"""Response DTO for POST /chat/summary."""

from models.base import PropertyAIBaseModel
from models.shared.user_needs import UserNeeds


class ChatSummaryResponse(PropertyAIBaseModel):
    """Outbound payload from the summary endpoint."""

    summary_text: str
    structured: UserNeeds
