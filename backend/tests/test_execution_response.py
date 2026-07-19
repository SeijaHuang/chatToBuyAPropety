"""Tests for models.shared.execution_response — ExecutionResponse."""

import json
from typing import Any

from models.base import ErrorDetail
from models.shared.execution_response import EExecutionStatus, ExecutionResponse


class TestExecutionResponse:
    """ExecutionResponse serialization and deserialization tests."""

    def test_success_with_data_serializes_correctly(self) -> None:
        """SUCCESS status with data produces correct JSON with camelCase keys."""
        response: ExecutionResponse = ExecutionResponse(
            status=EExecutionStatus.SUCCESS,
            data={"suburbs": ["Richmond", "Hawthorn"]},
        )
        raw: str = response.model_dump_json(by_alias=True, exclude_none=True)
        parsed: dict[str, Any] = json.loads(raw)

        assert parsed["status"] == "success"
        assert parsed["data"] == {"suburbs": ["Richmond", "Hawthorn"]}
        assert "error" not in parsed

    def test_failed_with_error_serializes_correctly(self) -> None:
        """FAILED status with ErrorDetail produces correct JSON."""
        error: ErrorDetail = ErrorDetail(
            code="GEOCODE_FAILED",
            message="Could not resolve address.",
            details={"address": "123 Main St"},
        )
        response: ExecutionResponse = ExecutionResponse(
            status=EExecutionStatus.FAILED,
            error=error,
        )
        raw: str = response.model_dump_json(by_alias=True, exclude_none=True)
        parsed: dict[str, Any] = json.loads(raw)

        assert parsed["status"] == "failed"
        assert "data" not in parsed
        assert parsed["error"]["code"] == "GEOCODE_FAILED"
        assert parsed["error"]["message"] == "Could not resolve address."
        assert parsed["error"]["details"] == {"address": "123 Main St"}

    def test_partial_status_serializes(self) -> None:
        """PARTIAL status serializes correctly."""
        response: ExecutionResponse = ExecutionResponse(
            status=EExecutionStatus.PARTIAL,
            data={"reply": "查询超时。请尝试更具体的问题。"},
        )
        raw: str = response.model_dump_json(by_alias=True)
        parsed: dict[str, Any] = json.loads(raw)

        assert parsed["status"] == "partial"
        assert parsed["data"] == {"reply": "查询超时。请尝试更具体的问题。"}

    def test_error_none_excluded_from_json(self) -> None:
        """When error is None, it does not appear in JSON output."""
        response: ExecutionResponse = ExecutionResponse(
            status=EExecutionStatus.SUCCESS,
            data="some result",
            error=None,
        )
        raw: str = response.model_dump_json(by_alias=True, exclude_none=True)
        parsed: dict[str, Any] = json.loads(raw)

        assert "error" not in parsed

    def test_roundtrip_json_to_model_validate(self) -> None:
        """JSON → model_validate → fields match original."""
        original: ExecutionResponse = ExecutionResponse(
            status=EExecutionStatus.SUCCESS,
            data={"key": "value"},
        )
        raw: str = original.model_dump_json(by_alias=True)
        restored: ExecutionResponse = ExecutionResponse.model_validate_json(raw)

        assert restored.status == EExecutionStatus.SUCCESS
        assert restored.data == {"key": "value"}
        assert restored.error is None

    def test_failed_roundtrip_preserves_error_detail(self) -> None:
        """FAILED status roundtrip preserves nested ErrorDetail."""
        error: ErrorDetail = ErrorDetail(
            code="TIMEOUT",
            message="Request timed out.",
        )
        original: ExecutionResponse = ExecutionResponse(
            status=EExecutionStatus.FAILED,
            error=error,
        )
        raw: str = original.model_dump_json(by_alias=True)
        restored: ExecutionResponse = ExecutionResponse.model_validate_json(raw)

        assert restored.status == EExecutionStatus.FAILED
        assert restored.error is not None
        assert restored.error.code == "TIMEOUT"
        assert restored.error.message == "Request timed out."

    def test_camelcase_alias_on_status_field(self) -> None:
        """status field serializes as 'status' (no change for lowercase)."""
        response: ExecutionResponse = ExecutionResponse(
            status=EExecutionStatus.SUCCESS,
            data=None,
        )
        raw: str = response.model_dump_json(by_alias=True)

        assert '"status"' in raw
        assert '"success"' in raw

    def test_data_can_be_primitive(self) -> None:
        """data field accepts primitive types (str, int, etc.)."""
        response: ExecutionResponse = ExecutionResponse(
            status=EExecutionStatus.SUCCESS,
            data="plain text result",
        )
        raw: str = response.model_dump_json(by_alias=True)
        parsed: dict[str, Any] = json.loads(raw)

        assert parsed["data"] == "plain text result"
