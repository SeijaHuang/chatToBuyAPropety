"""Protocol for intent-specific deterministic execution plans (PRD §S4.1).

Implementations (not in this subtask):
  - RecommendSuburbsHandler
  - ListPropertiesHandler
  - PropertyDetailHandler

Each implementation defines which Tools to call, in what order,
and how to compose their results.
"""

from typing import Protocol

from agent.shared.context import ExecutionContext
from models.shared.enums import EUserIntent


class IntentHandler[TIntentResult](Protocol):
    """Protocol for intent-specific deterministic execution plans.

    Implementations compose Tool calls in a deterministic order and
    return a structured result.  Structural subtyping — no explicit
    inheritance required.
    """

    async def execute_async(self, context: ExecutionContext) -> TIntentResult:
        """Execute the full deterministic plan for this intent.

        Args:
            context: Immutable execution context built by ContextResolver.

        Returns:
            The structured result for this intent (e.g. a list of suburbs).
        """
        ...

    @property
    def intent(self) -> EUserIntent:
        """The EUserIntent this handler is responsible for."""
        ...
