"""Service-layer result for POST /chat/summary."""

from dataclasses import dataclass

from models.shared.user_needs import UserNeeds


@dataclass(frozen=True)
class ChatSummaryDTO:
    """Outcome of generating a natural-language requirements summary.

    Attributes:
        summary_text: LLM-generated summary covering all non-None collected fields.
        user_needs: Part 1 → Part 2 handoff snapshot built from the same data.
    """

    summary_text: str
    user_needs: UserNeeds
