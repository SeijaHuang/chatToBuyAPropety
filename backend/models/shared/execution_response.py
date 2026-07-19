"""Unified result envelope returned by all Executors (PRD §S4.7)."""

from enum import StrEnum

from models.base import ErrorDetail, PropertyAIBaseModel


class EExecutionStatus(StrEnum):
    """Outcome status for an execution."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class ExecutionResponse(PropertyAIBaseModel):
    """Unified result envelope returned by all Executors.

    Crosses the Executor → Orchestrator → (future) HTTP boundary.
    Serialises with camelCase aliases via PropertyAIBaseModel.
    """

    status: EExecutionStatus
    data: object = None
    error: ErrorDetail | None = None
