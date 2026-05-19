"""Builds a UserNeeds snapshot from CollectedData (PRD §12.2)."""

from datetime import UTC, datetime

from models.conversation_state import CollectedData, EUserIntent
from models.user_needs import UserNeeds


def build_user_needs(
    collected: CollectedData,
    session_id: str,
    initial_intent: EUserIntent = EUserIntent.OPEN_ENDED_QUERY,
) -> UserNeeds:
    """Assemble a UserNeeds snapshot from CollectedData.

    Args:
        collected: Accumulated conversation data across all modules.
        session_id: Unique identifier for the conversation session.
        initial_intent: Routing intent classified at conversation start.

    Returns:
        UserNeeds snapshot for Part 1 → Part 2 handoff.
    """
    return UserNeeds(
        session_id=session_id,
        generated_at=datetime.now(tz=UTC),
        collected=collected,
        initial_intent=initial_intent,
    )
