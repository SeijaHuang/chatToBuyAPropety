"""Layer 2 — Global name → Tool registry.

ToolRegistry connects Handlers and Executors to Tool instances.
It delegates provider-specific schema wrapping to dedicated methods
so that BaseTool remains LLM-provider-agnostic.

Consumers in other modules (Handler, Executor) depend on IToolRegistry,
not on the concrete ToolRegistry — satisfying the Dependency Inversion
principle (SOLID-D).
"""

from __future__ import annotations

from typing import Any, Protocol

from agent.tool.base import BaseTool


class IToolRegistry(Protocol):
    """Protocol contract for tool registration and lookup.

    High-level modules (Handler, Executor) depend on this Protocol,
    not on the concrete ToolRegistry implementation.
    """

    def register(self, tool: BaseTool[Any]) -> None:
        """Register a Tool instance. Duplicate names raise ValueError."""
        ...

    def get(self, name: str) -> BaseTool[Any]:
        """Return a Tool by name. Raises KeyError if not found."""
        ...

    def list_names(self) -> list[str]:
        """Return the names of all registered Tools."""
        ...

    def get_tool_schemas(self) -> list[dict[str, object]]:
        """Return provider-agnostic metadata for every registered Tool."""
        ...

    def get_openai_tool_schemas(self) -> list[dict[str, object]]:
        """Return OpenAI function-calling definitions for every registered Tool."""
        ...


class ToolRegistry(IToolRegistry):
    """Global registry of all Atomic Tool instances.

    Tools are registered at application startup and never removed.
    Two consumers:
      - CodeDriven Handler:  registry.get("ptv_nearby_stops") → Tool instance
      - LLMDriven Executor:  registry.get_openai_tool_schemas() → OpenAI function-calling definitions
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool[Any]] = {}

    # ── Registration ────────────────────────────────────────────────────

    def register(self, tool: BaseTool[Any]) -> None:
        """Register a Tool instance. Duplicate names raise ValueError."""
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool[Any]:
        """Return a Tool by name. Raises KeyError if not found."""
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not found in registry")
        return self._tools[name]

    def list_names(self) -> list[str]:
        """Return the names of all registered Tools."""
        return list(self._tools.keys())

    # ── Schema generation ───────────────────────────────────────────────

    def get_tool_schemas(self) -> list[dict[str, object]]:
        """Return provider-agnostic metadata for every registered Tool.

        Each entry is {name, description, parameters} — the raw output
        of BaseTool.get_tool_schema() with no provider-specific envelope.
        """
        return [tool.get_tool_schema() for tool in self._tools.values()]

    def get_openai_tool_schemas(self) -> list[dict[str, object]]:
        """Return OpenAI function-calling definitions for every registered Tool.

        Wraps each provider-agnostic schema in the standard
        {"type": "function", "function": {...}} envelope expected by the
        OpenAI chat completions API.
        """
        return [{"type": "function", "function": schema} for schema in self.get_tool_schemas()]


def get_tool_registry() -> IToolRegistry:
    """FastAPI dependency — returns a ToolRegistry as the IToolRegistry implementation."""
    return ToolRegistry()
