"""Protocol for execution strategies dispatched by Orchestrator (PRD §S4.2).

Implementations:
  - CodeDrivenExecutor: intent → IntentHandler → deterministic workflow
  - LLMDrivenExecutor:  LLM loop + tool calling for open-ended queries
"""

from typing import Protocol

from agent.shared.context import ExecutionContext
from models.shared.execution_response import ExecutionResponse


class IExecutor(Protocol):
    """Protocol for execution strategies dispatched by Orchestrator.

    Each implementation takes an ExecutionContext and returns a
    unified ExecutionResponse. The caller (Orchestrator) does not
    need to know which strategy was used.
    """

    async def execute_async(self, context: ExecutionContext) -> ExecutionResponse:
        """Execute the strategy and return the final result."""
        ...
