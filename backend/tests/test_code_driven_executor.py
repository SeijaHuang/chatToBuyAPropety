"""Tests for agent.orchestration.executors.code_driven_executor."""

from unittest.mock import AsyncMock

import pytest

from agent.orchestration.executors.code_driven_executor import CodeDrivenExecutor
from agent.orchestration.handlers.base import IntentHandler
from agent.shared.context import ExecutionContext
from models.shared.enums import EUserIntent
from models.shared.execution_response import EExecutionStatus, ExecutionResponse
from models.shared.submodels import CollectedData

# ============================================================================
# Test doubles
# ============================================================================


class StubSuburbsHandler(IntentHandler[dict[str, object]]):
    """Fake handler that returns a list of suburbs."""

    @property
    def intent(self) -> EUserIntent:
        return EUserIntent.RECOMMEND_SUBURBS

    async def execute_async(self, context: ExecutionContext) -> dict[str, object]:
        return {"suburbs": ["Richmond", "Hawthorn"]}


class StubPropertiesHandler(IntentHandler[dict[str, object]]):
    """Fake handler for LIST_PROPERTIES intent."""

    @property
    def intent(self) -> EUserIntent:
        return EUserIntent.LIST_PROPERTIES

    async def execute_async(self, context: ExecutionContext) -> dict[str, object]:
        return {"properties": [{"id": "1", "address": "123 Main St"}]}


class PydanticResultHandler(IntentHandler[object]):
    """Fake handler that returns a Pydantic model."""

    @property
    def intent(self) -> EUserIntent:
        return EUserIntent.PROPERTY_DETAIL

    async def execute_async(self, context: ExecutionContext) -> object:
        from models.base import PropertyAIBaseModel

        class DetailResult(PropertyAIBaseModel):
            property_id: str
            price: int

        return DetailResult(property_id="prop-1", price=800000)


class ErrorHandler(IntentHandler[object]):
    """Fake handler that always raises."""

    @property
    def intent(self) -> EUserIntent:
        return EUserIntent.COMPARE_PROPERTIES

    async def execute_async(self, context: ExecutionContext) -> object:
        raise RuntimeError("Handler failure")


# ============================================================================
# Helpers
# ============================================================================


def _make_context(intent: EUserIntent = EUserIntent.RECOMMEND_SUBURBS) -> ExecutionContext:
    """Return a minimal ExecutionContext for the given intent."""
    collected: CollectedData = CollectedData()
    return ExecutionContext(
        session_id="test-session",
        intent=intent,
        user_needs=collected,
    )


# ============================================================================
# Tests
# ============================================================================


class TestCodeDrivenExecutor:
    """CodeDrivenExecutor tests — routing, result wrapping, and error cases."""

    @pytest.mark.anyio
    async def test_routes_to_correct_handler(self) -> None:
        """The handler matching the context's intent is called."""
        context: ExecutionContext = _make_context(EUserIntent.RECOMMEND_SUBURBS)
        handler: StubSuburbsHandler = StubSuburbsHandler()
        executor: CodeDrivenExecutor = CodeDrivenExecutor(
            handlers={EUserIntent.RECOMMEND_SUBURBS: handler}
        )

        response: ExecutionResponse = await executor.execute_async(context)

        assert response.status == EExecutionStatus.SUCCESS
        assert response.data == {"suburbs": ["Richmond", "Hawthorn"]}

    @pytest.mark.anyio
    async def test_routes_to_different_handler_by_intent(self) -> None:
        """When multiple handlers are registered, the right one is selected."""
        suburbs_handler: StubSuburbsHandler = StubSuburbsHandler()
        props_handler: StubPropertiesHandler = StubPropertiesHandler()
        executor: CodeDrivenExecutor = CodeDrivenExecutor(
            handlers={
                EUserIntent.RECOMMEND_SUBURBS: suburbs_handler,
                EUserIntent.LIST_PROPERTIES: props_handler,
            }
        )

        context: ExecutionContext = _make_context(EUserIntent.LIST_PROPERTIES)
        response: ExecutionResponse = await executor.execute_async(context)

        assert response.status == EExecutionStatus.SUCCESS
        assert response.data == {"properties": [{"id": "1", "address": "123 Main St"}]}

    @pytest.mark.anyio
    async def test_unregistered_intent_raises_value_error(self) -> None:
        """An intent with no matching handler raises ValueError."""
        executor: CodeDrivenExecutor = CodeDrivenExecutor(handlers={})
        context: ExecutionContext = _make_context(EUserIntent.OPEN_ENDED_QUERY)

        with pytest.raises(ValueError, match="No handler registered for intent"):
            await executor.execute_async(context)

    @pytest.mark.anyio
    async def test_wraps_pydantic_model_result(self) -> None:
        """A handler returning a Pydantic model is wrapped correctly."""
        handler: PydanticResultHandler = PydanticResultHandler()
        executor: CodeDrivenExecutor = CodeDrivenExecutor(
            handlers={EUserIntent.PROPERTY_DETAIL: handler}
        )
        context: ExecutionContext = _make_context(EUserIntent.PROPERTY_DETAIL)

        response: ExecutionResponse = await executor.execute_async(context)

        assert response.status == EExecutionStatus.SUCCESS
        assert response.data is not None

    @pytest.mark.anyio
    async def test_handler_exception_propagates(self) -> None:
        """When a handler raises, the exception propagates to the caller."""
        handler: ErrorHandler = ErrorHandler()
        executor: CodeDrivenExecutor = CodeDrivenExecutor(
            handlers={EUserIntent.COMPARE_PROPERTIES: handler}
        )
        context: ExecutionContext = _make_context(EUserIntent.COMPARE_PROPERTIES)

        with pytest.raises(RuntimeError, match="Handler failure"):
            await executor.execute_async(context)

    @pytest.mark.anyio
    async def test_empty_handlers_dict_raises_value_error(self) -> None:
        """An empty handlers mapping always raises ValueError for any intent."""
        executor: CodeDrivenExecutor = CodeDrivenExecutor(handlers={})
        context: ExecutionContext = _make_context(EUserIntent.RECOMMEND_SUBURBS)

        with pytest.raises(ValueError):
            await executor.execute_async(context)

    @pytest.mark.anyio
    async def test_mock_handler_called_with_context(self) -> None:
        """The handler receives the ExecutionContext passed by the executor."""
        mock_handler: AsyncMock = AsyncMock(spec=IntentHandler)
        mock_handler.intent = EUserIntent.RECOMMEND_SUBURBS
        mock_handler.execute_async.return_value = {"result": "mock"}
        executor: CodeDrivenExecutor = CodeDrivenExecutor(
            handlers={EUserIntent.RECOMMEND_SUBURBS: mock_handler}
        )
        context: ExecutionContext = _make_context(EUserIntent.RECOMMEND_SUBURBS)

        await executor.execute_async(context)

        mock_handler.execute_async.assert_awaited_once_with(context)
