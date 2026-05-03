"""Single source of truth for all Pydantic request/response models and domain DTOs."""

# TODO: Implementation: Story S-B
from pydantic import BaseModel


class ConversationStateDTO(BaseModel):
    """Placeholder DTO — full implementation in Story S-B."""

    session_id: str
    current_module: str
    status: str
    collected_data: dict[str, object]
    messages: list[dict[str, str]]
