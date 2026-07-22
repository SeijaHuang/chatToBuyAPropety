"""Tests for agent.shared.tool_result — ToolResult model."""

from datetime import UTC, datetime

from agent.tools.result import ToolResult


class TestToolResult:
    """ToolResult model tests."""

    def test_success_path_data_populated(self) -> None:
        """success=True sets data and leaves error fields as None."""
        result: ToolResult = ToolResult(
            success=True,
            data={"key": "value"},
            source="test_tool",
            execution_time_ms=42,
        )
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error_code is None
        assert result.error_message is None

    def test_failure_path_error_populated(self) -> None:
        """success=False sets error_code/error_message and leaves data as None."""
        result: ToolResult = ToolResult(
            success=False,
            error_code="TEST_ERROR",
            error_message="Something went wrong",
            source="test_tool",
            execution_time_ms=99,
        )
        assert result.success is False
        assert result.error_code == "TEST_ERROR"
        assert result.error_message == "Something went wrong"
        assert result.data is None

    def test_fallback_with_cached_at(self) -> None:
        """fallback=True with cached_at represents a stale-cache result."""
        now: datetime = datetime.now(tz=UTC)
        result: ToolResult = ToolResult(
            success=True,
            data={"stale": True},
            source="test_tool",
            execution_time_ms=0,
            fallback=True,
            cached_at=now,
        )
        assert result.fallback is True
        assert result.cached_at == now

    def test_camelcase_serialization(self) -> None:
        """model_dump(by_alias=True) produces camelCase keys via PropertyAIBaseModel."""
        result: ToolResult = ToolResult(
            success=True,
            data={"nearby_stops": 5},
            source="ptv_nearby_stops",
            execution_time_ms=150,
        )
        dumped: dict[str, object] = result.model_dump(by_alias=True)
        assert "success" in dumped
        assert "data" in dumped
        assert "source" in dumped
        assert "executionTimeMs" in dumped
        assert "errorCode" in dumped
        assert "errorMessage" in dumped
        assert "fallback" in dumped
        assert "cachedAt" in dumped

    def test_source_and_execution_time_preserved(self) -> None:
        """source and execution_time_ms are correctly stored."""
        result: ToolResult = ToolResult(
            success=True,
            source="ptv_nearby_stops",
            execution_time_ms=250,
        )
        assert result.source == "ptv_nearby_stops"
        assert result.execution_time_ms == 250
