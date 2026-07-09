"""Full session-state DTO for a single user conversation."""

from pydantic import Field

from models.base import PropertyAIBaseModel
from models.shared.enums import EModule, EStatus, EUserIntent
from models.shared.financial import BorrowingCapacityResult, BudgetGapResult
from models.shared.submodels import CollectedData, CompletionStatus


class ConversationStateDTO(PropertyAIBaseModel):
    """Full session state for a single user conversation.

    Serialises to camelCase JSON for API transport while retaining
    snake_case access internally via populate_by_name.
    """

    session_id: str
    status: EStatus = EStatus.IN_PROGRESS
    current_module: EModule = EModule.M1_PROPERTY_NEEDS
    completion_status: CompletionStatus = Field(default_factory=CompletionStatus)
    collected_data: CollectedData = Field(default_factory=CollectedData)
    conversation_history: list[dict[str, object]] = Field(default_factory=list)
    initial_intent: EUserIntent | None = None
    final_needs: CollectedData | None = None
    borrowing_capacity: BorrowingCapacityResult | None = None
    budget_gap: BudgetGapResult | None = None
