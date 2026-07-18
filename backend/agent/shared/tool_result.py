"""Layer 0 — Unified result type for all Atomic Tools."""

from datetime import datetime

from models.base import PropertyAIBaseModel


class ToolResult(PropertyAIBaseModel):
    """Unified result from any Atomic Tool.

    Every Tool.run() returns this — success or failure.
    Composers and Executors consume this without knowing which Tool produced it.
    """

    success: bool
    data: dict[str, object] | None = None
    error_code: str | None = None
    error_message: str | None = None
    source: str
    execution_time_ms: int
    fallback: bool = False
    cached_at: datetime | None = None
