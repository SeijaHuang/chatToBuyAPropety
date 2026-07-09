"""Lightweight conversation state snapshot reused by post_chat and get_chat responses."""

from models.base import PropertyAIBaseModel
from models.shared.enums import EModule, EStatus
from models.shared.financial import BorrowingCapacityResult, BudgetGapResult
from models.shared.submodels import CollectedData, CompletionStatus


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
