"""Tests for agent.orchestration.executors.llm_driven_executor — LLMDrivenExecutor."""

from typing import Any

import pytest
from pydantic import BaseModel

from agent.orchestration.executors.llm_driven_executor import LLMDrivenExecutor
from agent.shared.context import ExecutionContext
from agent.tool_registry.registry import ToolRegistry
from agent.tools.base import BaseTool
from models.shared.enums import EUserIntent
from models.shared.execution_response import EExecutionStatus, ExecutionResponse
from models.shared.submodels import CollectedData

# ============================================================================
# Test doubles — LLM
# ============================================================================


class FakeLLMClient:
    """Configurable fake LLM client implementing ILLMClient Protocol.

    Each test sets ``tool_call_responses`` to a list of dicts the LLM should
    return on successive calls to chat_with_tools_async.
    """

    def __init__(self, tool_call_responses: list[dict[str, Any]] | None = None) -> None:
        self.tool_call_responses: list[dict[str, Any]] = (
            tool_call_responses if tool_call_responses is not None else []
        )
        self._call_count: int = 0
        self.last_messages: list[dict[str, Any]] = []
        self.last_tools: list[dict[str, Any]] = []

    async def chat_with_tools_async(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Return the next configured response or {} when exhausted."""
        self.last_messages = messages
        self.last_tools = tools
        if self._call_count < len(self.tool_call_responses):
            response: dict[str, Any] = self.tool_call_responses[self._call_count]
            self._call_count += 1
            return response
        return {}

    async def complete_async(
        self,
        system_prompt: str,
        user_message: str,
    ) -> str:
        """Not used by LLMDrivenExecutor — present for Protocol compliance."""
        return ""


# ============================================================================
# Test doubles — Tool
# ============================================================================


class StubToolParams(BaseModel):
    """Params model for StubTool."""

    query: str = ""


class StubTool(BaseTool[StubToolParams]):
    """A simple tool used in LLMDrivenExecutor tests."""

    name: str = "stub_tool"
    description: str = "A stub tool for testing"
    params_model: type[StubToolParams] = StubToolParams

    def build_params(self, context: ExecutionContext) -> StubToolParams:
        return StubToolParams()

    async def _execute_async(self, params: StubToolParams) -> dict[str, Any]:
        return {"result": f"executed with query={params.query}"}


class AnotherStubTool(BaseTool[StubToolParams]):
    """A second tool for multi-tool registry tests."""

    name: str = "another_tool"
    description: str = "Another stub"
    params_model: type[StubToolParams] = StubToolParams

    def build_params(self, context: ExecutionContext) -> StubToolParams:
        return StubToolParams()

    async def _execute_async(self, params: StubToolParams) -> dict[str, Any]:
        return {"result": "another executed"}


# ============================================================================
# Helpers
# ============================================================================


def _make_context() -> ExecutionContext:
    """Return a minimal ExecutionContext."""
    collected: CollectedData = CollectedData()
    return ExecutionContext(
        session_id="test-session",
        intent=EUserIntent.OPEN_ENDED_QUERY,
        user_needs=collected,
        property_lat=-37.8136,
        property_lng=144.9631,
        target_entity_label="Test Target",
    )


def _make_registry() -> ToolRegistry:
    """Return a ToolRegistry with StubTool registered."""
    registry: ToolRegistry = ToolRegistry()
    registry.register(StubTool())
    return registry


# ============================================================================
# Tests
# ============================================================================


class TestLLMDrivenExecutor:
    """LLMDrivenExecutor tests — tool calling loop and edge cases."""

    @pytest.mark.anyio
    async def test_no_tool_call_returns_success(self) -> None:
        """When LLM returns empty dict, executor returns SUCCESS."""
        llm: FakeLLMClient = FakeLLMClient(tool_call_responses=[{}])
        registry: ToolRegistry = _make_registry()
        executor: LLMDrivenExecutor = LLMDrivenExecutor(llm=llm, registry=registry)
        context: ExecutionContext = _make_context()

        response: ExecutionResponse = await executor.execute_async(context)

        assert response.status == EExecutionStatus.SUCCESS
        assert isinstance(response.data, dict)
        data: dict[str, Any] = response.data
        assert "reply" in data

    @pytest.mark.anyio
    async def test_tool_call_executes_and_feeds_back(self) -> None:
        """LLM returns a tool call → tool is executed → result fed back to LLM."""
        llm: FakeLLMClient = FakeLLMClient(
            tool_call_responses=[
                {"name": "stub_tool", "query": "find suburbs"},
                {},  # Second call: no more tool calls → SUCCESS
            ]
        )
        registry: ToolRegistry = _make_registry()
        executor: LLMDrivenExecutor = LLMDrivenExecutor(llm=llm, registry=registry)
        context: ExecutionContext = _make_context()

        response: ExecutionResponse = await executor.execute_async(context)

        assert response.status == EExecutionStatus.SUCCESS
        # Verify the tool result was fed back as a message
        assert len(llm.last_messages) >= 2  # system + tool result
        tool_message: dict[str, Any] = llm.last_messages[-1]
        assert tool_message["role"] == "tool"
        assert "tool_call_id" in tool_message

    @pytest.mark.anyio
    async def test_max_rounds_exceeded_returns_partial(self) -> None:
        """When all rounds produce tool calls, executor returns PARTIAL."""
        # LLM always returns a tool call — never stops
        llm: FakeLLMClient = FakeLLMClient(
            tool_call_responses=[{"name": "stub_tool", "query": "q"}] * 10
        )
        registry: ToolRegistry = _make_registry()
        executor: LLMDrivenExecutor = LLMDrivenExecutor(llm=llm, registry=registry, max_rounds=3)
        context: ExecutionContext = _make_context()

        response: ExecutionResponse = await executor.execute_async(context)

        assert response.status == EExecutionStatus.PARTIAL
        assert isinstance(response.data, dict)
        data: dict[str, Any] = response.data
        assert "reply" in data

    @pytest.mark.anyio
    async def test_system_message_contains_session_id(self) -> None:
        """_build_system_message includes the session ID."""
        llm: FakeLLMClient = FakeLLMClient(tool_call_responses=[{}])
        registry: ToolRegistry = _make_registry()
        executor: LLMDrivenExecutor = LLMDrivenExecutor(llm=llm, registry=registry)
        context: ExecutionContext = _make_context()

        await executor.execute_async(context)

        system_msg: dict[str, Any] = llm.last_messages[0]
        content: str = str(system_msg["content"])
        assert "test-session" in content

    @pytest.mark.anyio
    async def test_system_message_contains_user_needs(self) -> None:
        """_build_system_message includes serialized user preferences."""
        llm: FakeLLMClient = FakeLLMClient(tool_call_responses=[{}])
        registry: ToolRegistry = _make_registry()
        executor: LLMDrivenExecutor = LLMDrivenExecutor(llm=llm, registry=registry)
        context: ExecutionContext = _make_context()

        await executor.execute_async(context)

        system_msg: dict[str, Any] = llm.last_messages[0]
        content: str = str(system_msg["content"])
        assert "User preferences" in content

    @pytest.mark.anyio
    async def test_system_message_contains_coordinates(self) -> None:
        """_build_system_message includes property location when coordinates are set."""
        llm: FakeLLMClient = FakeLLMClient(tool_call_responses=[{}])
        registry: ToolRegistry = _make_registry()
        executor: LLMDrivenExecutor = LLMDrivenExecutor(llm=llm, registry=registry)
        context: ExecutionContext = _make_context()

        await executor.execute_async(context)

        system_msg: dict[str, Any] = llm.last_messages[0]
        content: str = str(system_msg["content"])
        assert "lat=-37.8136" in content
        assert "lng=144.9631" in content

    @pytest.mark.anyio
    async def test_system_message_contains_target_label(self) -> None:
        """_build_system_message includes target_entity_label when set."""
        llm: FakeLLMClient = FakeLLMClient(tool_call_responses=[{}])
        registry: ToolRegistry = _make_registry()
        executor: LLMDrivenExecutor = LLMDrivenExecutor(llm=llm, registry=registry)
        context: ExecutionContext = _make_context()

        await executor.execute_async(context)

        system_msg: dict[str, Any] = llm.last_messages[0]
        content: str = str(system_msg["content"])
        assert "Target: Test Target" in content

    @pytest.mark.anyio
    async def test_system_message_omits_coordinates_when_none(self) -> None:
        """_build_system_message does not include coordinates when they are None."""
        llm: FakeLLMClient = FakeLLMClient(tool_call_responses=[{}])
        registry: ToolRegistry = _make_registry()
        executor: LLMDrivenExecutor = LLMDrivenExecutor(llm=llm, registry=registry)
        collected: CollectedData = CollectedData()
        context: ExecutionContext = ExecutionContext(
            session_id="test-session",
            intent=EUserIntent.OPEN_ENDED_QUERY,
            user_needs=collected,
        )

        await executor.execute_async(context)

        system_msg: dict[str, Any] = llm.last_messages[0]
        content: str = str(system_msg["content"])
        assert "Property location" not in content

    @pytest.mark.anyio
    async def test_tool_schemas_passed_to_llm(self) -> None:
        """The executor passes OpenAI tool schemas to the LLM."""
        llm: FakeLLMClient = FakeLLMClient(tool_call_responses=[{}])
        registry: ToolRegistry = _make_registry()
        executor: LLMDrivenExecutor = LLMDrivenExecutor(llm=llm, registry=registry)
        context: ExecutionContext = _make_context()

        await executor.execute_async(context)

        assert len(llm.last_tools) > 0
        assert llm.last_tools[0]["type"] == "function"
        assert llm.last_tools[0]["function"]["name"] == "stub_tool"

    @pytest.mark.anyio
    async def test_custom_max_rounds(self) -> None:
        """max_rounds can be configured via constructor."""
        llm: FakeLLMClient = FakeLLMClient(
            tool_call_responses=[{"name": "stub_tool", "query": "q"}] * 10
        )
        registry: ToolRegistry = _make_registry()
        executor: LLMDrivenExecutor = LLMDrivenExecutor(llm=llm, registry=registry, max_rounds=1)
        context: ExecutionContext = _make_context()

        response: ExecutionResponse = await executor.execute_async(context)

        assert response.status == EExecutionStatus.PARTIAL
