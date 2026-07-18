"""Layer 0–2 shared types, base classes, and registry."""

from agent.shared.connector import (
    ConnectorError,
    ConnectorHttpError,
    ConnectorTimeoutError,
)
from agent.shared.execution_context import ExecutionContext
from agent.shared.execution_events import EExecutionEvent
from agent.shared.tool_result import ToolResult

__all__ = [
    "ToolResult",
    "ExecutionContext",
    "EExecutionEvent",
    "ConnectorError",
    "ConnectorHttpError",
    "ConnectorTimeoutError",
]
