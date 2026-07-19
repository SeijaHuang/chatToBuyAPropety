"""Tests for agent.orchestration.orchestrator — Orchestrator."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from agent.orchestration.context_resolver import ContextResolver
from agent.orchestration.executors.code_driven_executor import CodeDrivenExecutor
from agent.orchestration.executors.llm_driven_executor import LLMDrivenExecutor
from agent.orchestration.orchestrator import Orchestrator
from agent.shared.context import ExecutionContext
from models.shared.enums import EUserIntent
from models.shared.execution_response import EExecutionStatus, ExecutionResponse
from models.shared.routing import EExecutionMode, ETriggerSource, RoutingPayload
from models.shared.submodels import CollectedData
from models.shared.user_needs import UserNeeds

# ============================================================================
# Helpers
# ============================================================================


def _make_routing(
    execution_mode: EExecutionMode = EExecutionMode.CODE_DRIVEN,
    intent: EUserIntent = EUserIntent.RECOMMEND_SUBURBS,
) -> RoutingPayload:
    """Build a minimal RoutingPayload for orchestrator tests."""
    user_needs: UserNeeds = UserNeeds(
        session_id="test-session",
        generated_at=datetime.now(tz=UTC),
        collected=CollectedData(),
        initial_intent=intent,
    )
    return RoutingPayload(
        intent=intent,
        session_id="test-session",
        user_needs=user_needs,
        execution_mode=execution_mode,
        agents_hint=[],
        triggered_at=datetime.now(tz=UTC),
        trigger_source=ETriggerSource.AUTO_COMPLETE,
    )


# ============================================================================
# Tests
# ============================================================================


class TestOrchestrator:
    """Orchestrator tests — dispatch by execution_mode and call chain verification."""

    @pytest.mark.anyio
    async def test_code_driven_mode_dispatches_to_code_executor(self) -> None:
        """execution_mode=CODE_DRIVEN → CodeDrivenExecutor.execute_async called."""
        mock_resolver: AsyncMock = AsyncMock(spec=ContextResolver)
        mock_resolver.resolve_async.return_value = ExecutionContext(
            session_id="test-session",
            intent=EUserIntent.RECOMMEND_SUBURBS,
            user_needs=CollectedData(),
        )
        mock_code: AsyncMock = AsyncMock(spec=CodeDrivenExecutor)
        mock_code.execute_async.return_value = ExecutionResponse(
            status=EExecutionStatus.SUCCESS, data={"result": "code"}
        )
        mock_llm: AsyncMock = AsyncMock(spec=LLMDrivenExecutor)

        orchestrator: Orchestrator = Orchestrator(
            context_resolver=mock_resolver,
            code_driven_executor=mock_code,
            llm_driven_executor=mock_llm,
        )
        routing: RoutingPayload = _make_routing(EExecutionMode.CODE_DRIVEN)

        response: ExecutionResponse = await orchestrator.execute_async(routing)

        assert response.status == EExecutionStatus.SUCCESS
        assert response.data == {"result": "code"}
        mock_code.execute_async.assert_awaited_once()
        mock_llm.execute_async.assert_not_awaited()

    @pytest.mark.anyio
    async def test_agentic_loop_mode_dispatches_to_llm_executor(self) -> None:
        """execution_mode=AGENTIC_LOOP → LLMDrivenExecutor.execute_async called."""
        mock_resolver: AsyncMock = AsyncMock(spec=ContextResolver)
        mock_resolver.resolve_async.return_value = ExecutionContext(
            session_id="test-session",
            intent=EUserIntent.OPEN_ENDED_QUERY,
            user_needs=CollectedData(),
        )
        mock_code: AsyncMock = AsyncMock(spec=CodeDrivenExecutor)
        mock_llm: AsyncMock = AsyncMock(spec=LLMDrivenExecutor)
        mock_llm.execute_async.return_value = ExecutionResponse(
            status=EExecutionStatus.SUCCESS, data={"reply": "LLM answer"}
        )

        orchestrator: Orchestrator = Orchestrator(
            context_resolver=mock_resolver,
            code_driven_executor=mock_code,
            llm_driven_executor=mock_llm,
        )
        routing: RoutingPayload = _make_routing(EExecutionMode.AGENTIC_LOOP)

        response: ExecutionResponse = await orchestrator.execute_async(routing)

        assert response.status == EExecutionStatus.SUCCESS
        assert response.data == {"reply": "LLM answer"}
        mock_llm.execute_async.assert_awaited_once()
        mock_code.execute_async.assert_not_awaited()

    @pytest.mark.anyio
    async def test_context_resolver_called_before_executor(self) -> None:
        """ContextResolver.resolve_async is called before any executor."""
        call_order: list[str] = []
        mock_resolver: AsyncMock = AsyncMock(spec=ContextResolver)
        mock_code: AsyncMock = AsyncMock(spec=CodeDrivenExecutor)

        async def _resolver_side_effect(routing: RoutingPayload) -> ExecutionContext:
            call_order.append("resolver")
            return ExecutionContext(
                session_id="test-session",
                intent=EUserIntent.RECOMMEND_SUBURBS,
                user_needs=CollectedData(),
            )

        async def _code_side_effect(context: ExecutionContext) -> ExecutionResponse:
            call_order.append("executor")
            return ExecutionResponse(status=EExecutionStatus.SUCCESS)

        mock_resolver.resolve_async = _resolver_side_effect
        mock_code.execute_async = _code_side_effect
        mock_llm: AsyncMock = AsyncMock(spec=LLMDrivenExecutor)

        orchestrator: Orchestrator = Orchestrator(
            context_resolver=mock_resolver,
            code_driven_executor=mock_code,
            llm_driven_executor=mock_llm,
        )
        routing: RoutingPayload = _make_routing(EExecutionMode.CODE_DRIVEN)

        await orchestrator.execute_async(routing)

        assert call_order == ["resolver", "executor"]

    @pytest.mark.anyio
    async def test_execution_response_passthrough(self) -> None:
        """The executor's ExecutionResponse is returned unchanged."""
        expected: ExecutionResponse = ExecutionResponse(
            status=EExecutionStatus.PARTIAL,
            data={"partial": "result"},
        )
        mock_resolver: AsyncMock = AsyncMock(spec=ContextResolver)
        mock_resolver.resolve_async.return_value = ExecutionContext(
            session_id="test-session",
            intent=EUserIntent.OPEN_ENDED_QUERY,
            user_needs=CollectedData(),
        )
        mock_code: AsyncMock = AsyncMock(spec=CodeDrivenExecutor)
        mock_llm: AsyncMock = AsyncMock(spec=LLMDrivenExecutor)
        mock_llm.execute_async.return_value = expected

        orchestrator: Orchestrator = Orchestrator(
            context_resolver=mock_resolver,
            code_driven_executor=mock_code,
            llm_driven_executor=mock_llm,
        )
        routing: RoutingPayload = _make_routing(EExecutionMode.AGENTIC_LOOP)

        response: ExecutionResponse = await orchestrator.execute_async(routing)

        assert response is expected
