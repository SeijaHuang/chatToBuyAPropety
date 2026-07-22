"""Tests for agent.shared.tool — BaseTool generic base class."""

import pytest
from pydantic import BaseModel

from agent.connectors.base import ConnectorHttpError, ConnectorTimeoutError
from agent.shared.context import ExecutionContext
from agent.tools.base import BaseTool
from agent.tools.result import ToolResult
from models.shared.enums import EUserIntent
from models.shared.submodels import CollectedData

# ============================================================================
# Test doubles
# ============================================================================


class FakeToolParams(BaseModel):
    """Params model for FakeTool."""

    query: str
    limit: int = 10


class FakeTool(BaseTool[FakeToolParams]):
    """Minimal concrete tool for testing BaseTool."""

    name: str = "fake_tool"
    description: str = "A fake tool for testing"
    params_model: type[FakeToolParams] = FakeToolParams

    def build_params(self, context: ExecutionContext) -> FakeToolParams:
        return FakeToolParams(query="test-query")

    async def _execute_async(self, params: FakeToolParams) -> dict[str, object]:
        return {"query": params.query, "limit": params.limit}


class ErrorToolParams(BaseModel):
    """Params model for ErrorTool."""

    fail_with: str


class HttpErrorTool(BaseTool[ErrorToolParams]):
    """Tool whose _execute_async always raises ConnectorHttpError."""

    name: str = "http_error_tool"
    description: str = "Always fails with HTTP error"
    params_model: type[ErrorToolParams] = ErrorToolParams

    def build_params(self, context: ExecutionContext) -> ErrorToolParams:
        return ErrorToolParams(fail_with="http")

    async def _execute_async(self, params: ErrorToolParams) -> dict[str, object]:
        raise ConnectorHttpError(
            status_code=429,
            error_code="RATE_LIMITED",
            response_body='{"error": "Too many requests"}',
        )


class TimeoutTool(BaseTool[ErrorToolParams]):
    """Tool whose _execute_async always raises ConnectorTimeoutError."""

    name: str = "timeout_tool"
    description: str = "Always times out"
    params_model: type[ErrorToolParams] = ErrorToolParams

    def build_params(self, context: ExecutionContext) -> ErrorToolParams:
        return ErrorToolParams(fail_with="timeout")

    async def _execute_async(self, params: ErrorToolParams) -> dict[str, object]:
        raise ConnectorTimeoutError(path="/v3/stops", attempts=3)


class IncompleteTool(BaseTool[FakeToolParams]):
    """Tool missing abstract methods — used to verify ABC enforcement."""

    name: str = "incomplete"
    description: str = "missing abstract methods"
    params_model: type[FakeToolParams] = FakeToolParams


# ============================================================================
# Helpers
# ============================================================================


def _make_context() -> ExecutionContext:
    """Return a minimal ExecutionContext for tests."""
    collected: CollectedData = CollectedData()
    return ExecutionContext(
        session_id="test-session",
        intent=EUserIntent.OPEN_ENDED_QUERY,
        user_needs=collected,
    )


# ============================================================================
# BaseTool.run_async
# ============================================================================


class TestBaseToolRunAsync:
    """Tests for BaseTool.run_async — the template method."""

    @pytest.mark.anyio
    async def test_success_returns_tool_result_with_data(self) -> None:
        """On _execute_async success, returns ToolResult(success=True)."""
        tool: FakeTool = FakeTool()
        params: FakeToolParams = FakeToolParams(query="hello")
        result: ToolResult = await tool.run_async(params)

        assert result.success is True
        assert result.data == {"query": "hello", "limit": 10}
        assert result.source == "fake_tool"
        assert result.error_code is None
        assert result.error_message is None

    @pytest.mark.anyio
    async def test_connector_http_error_returns_failure_result(self) -> None:
        """ConnectorHttpError → ToolResult(success=False, error_code=e.error_code)."""
        tool: HttpErrorTool = HttpErrorTool()
        params: ErrorToolParams = ErrorToolParams(fail_with="http")
        result: ToolResult = await tool.run_async(params)

        assert result.success is False
        assert result.error_code == "RATE_LIMITED"
        assert result.error_message is not None
        assert "RATE_LIMITED" in (result.error_message or "")
        assert result.data is None
        assert result.source == "http_error_tool"

    @pytest.mark.anyio
    async def test_connector_timeout_error_returns_timeout_error_code(self) -> None:
        """ConnectorTimeoutError → ToolResult(success=False) + _TIMEOUT suffix."""
        tool: TimeoutTool = TimeoutTool()
        params: ErrorToolParams = ErrorToolParams(fail_with="timeout")
        result: ToolResult = await tool.run_async(params)

        assert result.success is False
        assert result.error_code == "TIMEOUT_TOOL_TIMEOUT"
        assert result.error_message is not None
        assert "timed out" in (result.error_message or "")
        assert result.data is None
        assert result.source == "timeout_tool"

    @pytest.mark.anyio
    async def test_execution_time_ms_is_reasonable(self) -> None:
        """execution_time_ms is computed correctly from wall-clock timing."""
        tool: FakeTool = FakeTool()
        params: FakeToolParams = FakeToolParams(query="timing-test")
        result: ToolResult = await tool.run_async(params)

        assert result.execution_time_ms >= 0
        # Should complete well under 1 second for a no-op tool.
        assert result.execution_time_ms < 1000

    @pytest.mark.anyio
    async def test_fallback_and_cached_at_defaults(self) -> None:
        """fallback is False and cached_at is None by default."""
        tool: FakeTool = FakeTool()
        params: FakeToolParams = FakeToolParams(query="defaults-test")
        result: ToolResult = await tool.run_async(params)

        assert result.fallback is False
        assert result.cached_at is None


# ============================================================================
# BaseTool.get_tool_schema
# ============================================================================


class TestBaseToolGetToolSchema:
    """Tests for BaseTool.get_tool_schema — provider-agnostic metadata."""

    def test_output_is_provider_agnostic(self) -> None:
        """Top-level keys are name, description, parameters only (no OpenAI envelope)."""
        tool: FakeTool = FakeTool()
        schema: dict[str, object] = tool.get_tool_schema()
        assert set(schema.keys()) == {"name", "description", "parameters"}
        assert "type" not in schema  # No OpenAI "type": "function" at top level

    def test_name_and_description_are_top_level(self) -> None:
        """name and description come from class attrs, at top level."""
        tool: FakeTool = FakeTool()
        schema: dict[str, object] = tool.get_tool_schema()
        assert schema["name"] == "fake_tool"
        assert schema["description"] == "A fake tool for testing"

    def test_parameters_has_type_properties_required(self) -> None:
        """parameters contains type, properties, and required."""
        tool: FakeTool = FakeTool()
        schema: dict[str, object] = tool.get_tool_schema()

        parameters: object = schema["parameters"]
        assert isinstance(parameters, dict)
        params: dict[str, object] = parameters

        assert params["type"] == "object"
        assert "properties" in params
        assert "required" in params

    def test_parameters_reflect_params_model_fields(self) -> None:
        """properties include query (str) and limit (int) from FakeToolParams."""
        tool: FakeTool = FakeTool()
        schema: dict[str, object] = tool.get_tool_schema()

        parameters: object = schema["parameters"]
        assert isinstance(parameters, dict)
        properties: object = parameters["properties"]
        assert isinstance(properties, dict)

        props: dict[str, object] = properties
        assert "query" in props
        assert "limit" in props

    def test_nested_model_includes_defs(self) -> None:
        """$defs are forwarded for nested Pydantic models."""

        class NestedItem(BaseModel):
            name: str

        class NestedParams(BaseModel):
            items: list[NestedItem]

        class NestedTool(BaseTool[NestedParams]):
            name: str = "nested_tool"
            description: str = "Tool with nested params"
            params_model: type[NestedParams] = NestedParams

            def build_params(self, context: ExecutionContext) -> NestedParams:
                return NestedParams(items=[])

            async def _execute_async(self, params: NestedParams) -> dict[str, object]:
                return {}

        tool: NestedTool = NestedTool()
        schema: dict[str, object] = tool.get_tool_schema()

        parameters: object = schema["parameters"]
        assert isinstance(parameters, dict)
        params: dict[str, object] = parameters
        assert "$defs" in params
        defs: object = params["$defs"]
        assert isinstance(defs, dict)
        assert "NestedItem" in defs


# ============================================================================
# BaseTool abstract methods
# ============================================================================


class TestBaseToolAbstract:
    """Verify that build_params and _execute_async are abstract."""

    def test_cannot_instantiate_without_concrete_methods(self) -> None:
        """Instantiating a subclass that doesn't implement abstract methods raises."""
        with pytest.raises(TypeError):
            IncompleteTool()  # type: ignore[abstract]

    def test_concrete_subclass_instantiates(self) -> None:
        """A fully-implemented subclass can be instantiated."""
        tool: FakeTool = FakeTool()
        assert tool.name == "fake_tool"
        assert tool.description == "A fake tool for testing"
        assert tool.params_model is FakeToolParams

    def test_build_params_is_callable(self) -> None:
        """build_params on a concrete tool returns the correct params type."""
        tool: FakeTool = FakeTool()
        context: ExecutionContext = _make_context()
        params: FakeToolParams = tool.build_params(context)
        assert isinstance(params, FakeToolParams)
        assert params.query == "test-query"
