"""Deterministic execution: intent → IntentHandler → structured result (PRD §S4.3)."""

from typing import Annotated

import structlog
from fastapi import Depends

from agent.orchestration.executors.base import IExecutor
from agent.orchestration.handlers.base import IntentHandler
from agent.shared.context import ExecutionContext
from models.shared.enums import EUserIntent
from models.shared.execution_response import EExecutionStatus, ExecutionResponse

logger = structlog.get_logger()


class CodeDrivenExecutor(IExecutor):
    """Deterministic execution: intent → IntentHandler → structured result."""

    def __init__(self, handlers: dict[EUserIntent, IntentHandler[object]]) -> None:
        """Initialise with a mapping of intents to their handlers.

        Args:
            handlers: Intent → Handler mapping. Each handler must handle
                      the intent returned by its ``intent`` property.
        """
        self._handlers: dict[EUserIntent, IntentHandler[object]] = handlers

    async def execute_async(self, context: ExecutionContext) -> ExecutionResponse:
        """Route to the matching IntentHandler and wrap the result.

        Args:
            context: Immutable execution context from ContextResolver.

        Returns:
            ExecutionResponse wrapping the handler's result.

        Raises:
            ValueError: When no handler is registered for context.intent.
        """
        handler: IntentHandler[object] | None = self._handlers.get(context.intent)
        if handler is None:
            raise ValueError(f"No handler registered for intent: {context.intent}")

        log: structlog.BoundLogger = logger.bind(
            session_id=context.session_id, intent=context.intent
        )
        log.info("code_driven_execution_start")

        result: object = await handler.execute_async(context)
        return ExecutionResponse(status=EExecutionStatus.SUCCESS, data=result)


def get_handlers() -> dict[EUserIntent, IntentHandler[object]]:
    """FastAPI dependency — returns the registered intent→handler mapping.

    Prototype placeholder: returns an empty dict.  Populate this with
    real IntentHandler instances (e.g. RecommendSuburbsHandler) once they
    are implemented.
    """
    return {}


def get_code_driven_executor(
    handlers: Annotated[dict[EUserIntent, IntentHandler[object]], Depends(get_handlers)],
) -> IExecutor:
    """FastAPI dependency — returns a CodeDrivenExecutor wired to its handlers."""
    return CodeDrivenExecutor(handlers=handlers)
