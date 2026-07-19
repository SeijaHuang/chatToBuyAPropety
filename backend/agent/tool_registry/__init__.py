"""Global name → Tool registry — connects Handlers and Executors to Tool instances."""

from agent.tool_registry.registry import IToolRegistry, ToolRegistry, get_tool_registry

__all__ = ["IToolRegistry", "ToolRegistry", "get_tool_registry"]
