"""Service-layer result for POST /chat."""

from dataclasses import dataclass

from models.shared.conversation_state import ConversationStateDTO
from models.shared.routing import RoutingPayload


@dataclass(frozen=True)
class ChatTurnDTO:
    """Outcome of processing one POST /chat turn.

    Attributes:
        reply: Assistant reply text from the Round 2 question-generation call.
        extracted: Fields extracted by Round 1 (empty dict on tool-call parse failure).
        state: Fully updated conversation state after this turn (already persisted).
        routing: Populated when the turn completes requirements or matches a keyword.
        should_persist: True when a Postgres upsert was performed this turn — true
            for a brand-new session or when any module newly completed this turn.
    """

    reply: str
    extracted: dict[str, object]
    state: ConversationStateDTO
    routing: RoutingPayload | None
    should_persist: bool
