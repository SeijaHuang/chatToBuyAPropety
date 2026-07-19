"""Part 2 entry point — resolve context and dispatch to Executor (PRD §S4.6)."""

from typing import Annotated, Protocol

import structlog
from fastapi import Depends

from agent.orchestration.context_resolver import IContextResolver, get_context_resolver
from agent.orchestration.executors.base import IExecutor
from agent.orchestration.executors.code_driven_executor import get_code_driven_executor
from agent.orchestration.executors.llm_driven_executor import get_llm_driven_executor
from agent.shared.context import ExecutionContext
from models.shared.execution_response import ExecutionResponse
from models.shared.routing import EExecutionMode, RoutingPayload

logger = structlog.get_logger()


class IOrchestrator(Protocol):
    """Protocol for Part 2 orchestration strategies.

    Receives a RoutingPayload from Part 1, resolves execution context,
    and dispatches to the appropriate IExecutor.
    """

    async def execute_async(self, routing: RoutingPayload) -> ExecutionResponse:
        """Resolve context and dispatch to the correct executor."""
        ...


class Orchestrator(IOrchestrator):
    """Part 2 entry point.

    Receives a RoutingPayload from Part 1, builds ExecutionContext,
    dispatches to the appropriate Executor based on execution_mode.
    """

    def __init__(
        self,
        context_resolver: IContextResolver,
        code_driven_executor: IExecutor,
        llm_driven_executor: IExecutor,
    ) -> None:
        """Initialise with all required dependencies.

        Args:
            context_resolver: Builds ExecutionContext from RoutingPayload.
            code_driven_executor: Handles CODE_DRIVEN execution mode.
            llm_driven_executor: Handles AGENTIC_LOOP execution mode.
        """
        self._context_resolver: IContextResolver = context_resolver
        self._code_driven_executor: IExecutor = code_driven_executor
        self._llm_driven_executor: IExecutor = llm_driven_executor

    async def execute_async(self, routing: RoutingPayload) -> ExecutionResponse:
        """Resolve context and dispatch to the correct executor.

        Args:
            routing: Routing payload from Part 1 with intent, mode, and user data.

        Returns:
            Unified ExecutionResponse from the selected executor.
        """
        log: structlog.BoundLogger = logger.bind(
            session_id=routing.session_id,
            intent=routing.intent,
            execution_mode=routing.execution_mode,
        )
        log.info("orchestrator_execution_start")

        context: ExecutionContext = await self._context_resolver.resolve_async(routing)

        if routing.execution_mode == EExecutionMode.CODE_DRIVEN:
            return await self._code_driven_executor.execute_async(context)

        return await self._llm_driven_executor.execute_async(context)


def get_orchestrator(
    context_resolver: Annotated[IContextResolver, Depends(get_context_resolver)],
    code_driven_executor: Annotated[IExecutor, Depends(get_code_driven_executor)],
    llm_driven_executor: Annotated[IExecutor, Depends(get_llm_driven_executor)],
) -> IOrchestrator:
    """FastAPI dependency — returns a fully-wired Orchestrator as IOrchestrator.

    Composes three sub-dependencies via FastAPI's Depends chain:
      - IContextResolver  → ContextResolver
      - IExecutor (CODE)  → CodeDrivenExecutor
      - IExecutor (LLM)   → LLMDrivenExecutor
    """
    return Orchestrator(
        context_resolver=context_resolver,
        code_driven_executor=code_driven_executor,
        llm_driven_executor=llm_driven_executor,
    )
