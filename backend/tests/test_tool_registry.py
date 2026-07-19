"""Tests for agent.shared.tool_registry — ToolRegistry."""

import pytest
from pydantic import BaseModel

from agent.shared.execution_context import ExecutionContext
from agent.shared.tool import BaseTool
from agent.shared.tool_registry import ToolRegistry

# ============================================================================
# Test doubles
# ============================================================================


class StubParams(BaseModel):
    query: str = ""


class StubTool(BaseTool[StubParams]):
    name: str = "stub_tool"
    description: str = "A stub tool"
    params_model: type[StubParams] = StubParams

    def build_params(self, context: ExecutionContext) -> StubParams:
        return StubParams()

    async def _execute_async(self, params: StubParams) -> dict[str, object]:
        return {}


class AnotherTool(BaseTool[StubParams]):
    name: str = "another_tool"
    description: str = "Another stub"
    params_model: type[StubParams] = StubParams

    def build_params(self, context: ExecutionContext) -> StubParams:
        return StubParams()

    async def _execute_async(self, params: StubParams) -> dict[str, object]:
        return {}


# ============================================================================
# Tests
# ============================================================================


class TestToolRegistry:
    """ToolRegistry tests — registration, lookup, and schema generation."""

    def test_register_and_get_roundtrip(self) -> None:
        """A registered tool is retrievable by name."""
        registry: ToolRegistry = ToolRegistry()
        tool: StubTool = StubTool()
        registry.register(tool)
        assert registry.get("stub_tool") is tool

    def test_list_names_includes_registered(self) -> None:
        """list_names() returns all registered tool names."""
        registry: ToolRegistry = ToolRegistry()
        registry.register(StubTool())
        registry.register(AnotherTool())
        names: list[str] = registry.list_names()
        assert sorted(names) == ["another_tool", "stub_tool"]

    def test_duplicate_name_raises_value_error(self) -> None:
        """Registering the same tool name twice raises ValueError."""
        registry: ToolRegistry = ToolRegistry()
        registry.register(StubTool())
        with pytest.raises(ValueError):
            registry.register(StubTool())

    def test_get_missing_raises_key_error(self) -> None:
        """Getting an unregistered name raises KeyError."""
        registry: ToolRegistry = ToolRegistry()
        with pytest.raises(KeyError):
            registry.get("nonexistent")

    def test_get_tool_schemas_empty_registry(self) -> None:
        """An empty registry returns an empty list."""
        registry: ToolRegistry = ToolRegistry()
        assert registry.get_tool_schemas() == []

    def test_get_tool_schemas_is_provider_agnostic(self) -> None:
        """get_tool_schemas() returns {name, description, parameters} per tool."""
        registry: ToolRegistry = ToolRegistry()
        registry.register(StubTool())
        schemas: list[dict[str, object]] = registry.get_tool_schemas()
        assert len(schemas) == 1
        assert set(schemas[0].keys()) == {"name", "description", "parameters"}

    def test_get_openai_tool_schemas_wraps_with_envelope(self) -> None:
        """get_openai_tool_schemas() wraps each schema in {type, function}."""
        registry: ToolRegistry = ToolRegistry()
        registry.register(StubTool())
        schemas: list[dict[str, object]] = registry.get_openai_tool_schemas()
        assert len(schemas) == 1
        assert schemas[0]["type"] == "function"
        assert isinstance(schemas[0]["function"], dict)
        func: dict[str, object] = schemas[0]["function"]
        assert func["name"] == "stub_tool"
        assert func["description"] == "A stub tool"
        assert "parameters" in func

    def test_get_openai_tool_schemas_empty_registry(self) -> None:
        """An empty registry returns an empty list for OpenAI schemas too."""
        registry: ToolRegistry = ToolRegistry()
        assert registry.get_openai_tool_schemas() == []
