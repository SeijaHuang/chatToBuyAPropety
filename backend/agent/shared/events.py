"""Layer 0 — SSE event type enumeration for execution streaming."""

from enum import StrEnum


class EExecutionEvent(StrEnum):
    """SSE event types emitted during agent execution.

    Used by Executor implementations to stream progress events
    to the frontend via Server-Sent Events.
    """

    EXECUTION_STARTED = "execution_started"
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"
    TOOL_FAILED = "tool_failed"
    SUMMARY_STARTED = "summary_started"
    SUMMARY_COMPLETED = "summary_completed"
    SYNTHESIS_STARTED = "synthesis_started"
    SYNTHESIS_CHUNK = "synthesis_chunk"
    SYNTHESIS_COMPLETED = "synthesis_completed"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
