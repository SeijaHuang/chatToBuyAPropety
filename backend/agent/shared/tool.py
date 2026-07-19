"""Layer 1 — Generic Atomic Tool base class.

BaseTool[TParams] is the single template all Atomic Tools inherit from.
It owns timing, error→ToolResult conversion, and provider-agnostic schema
generation, so individual Tools only implement build_params and
_execute_async.

The OpenAI function-calling envelope is applied at the ToolRegistry /
Executor layer — Tools themselves are provider-agnostic.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import TypeVar, cast

from pydantic import BaseModel

from agent.shared.connector import ConnectorHttpError, ConnectorTimeoutError
from agent.shared.execution_context import ExecutionContext
from agent.shared.tool_result import ToolResult

TToolParams = TypeVar("TToolParams", bound=BaseModel)


class BaseTool[TToolParams](ABC):
    """Generic base for all Atomic Tools.

    Type parameter TToolParams is the Pydantic model describing the tool's
    resolved input parameters (built by build_params from ExecutionContext).

    Subclasses override three class attributes and two methods:

        name: str           — unique tool identifier (e.g. "ptv_nearby_stops")
        description: str    — human-readable, used in LLM function descriptions
        params_model: type[TToolParams]  — Pydantic model for parameter validation

        build_params(context) → TToolParams     — pure, no I/O
        _execute_async(params) → dict       — calls Connector, returns raw data
    """

    # ── Subclass overrides (class attributes) ───────────────────────────

    name: str
    description: str
    params_model: type[TToolParams]

    # ── Abstract interface ──────────────────────────────────────────────

    @abstractmethod
    def build_params(self, context: ExecutionContext) -> TToolParams:
        """Build tool-specific params from the shared ExecutionContext.

        Pure function — no I/O, no side effects.
        Each Tool extracts only the fields it needs from the context.
        """
        ...

    @abstractmethod
    async def _execute_async(self, params: TToolParams) -> dict[str, object]:
        """Execute the tool's core logic against its external API.

        Args:
            params: Resolved parameters from build_params().

        Returns:
            Raw result dict from the connector (the "data" payload).
            This dict must be JSON-serialisable.

        Raises:
            ConnectorHttpError: On non-2xx HTTP response.
            ConnectorTimeoutError: When retries are exhausted.
        """
        ...

    # ── Template method ─────────────────────────────────────────────────

    async def run_async(self, params: TToolParams) -> ToolResult:
        """Execute the tool and wrap the outcome in a unified ToolResult.

        Template method — subclasses do NOT override this.  It owns:
        - Wall-clock timing
        - ConnectorError → ToolResult(success=False) conversion
        - Timeout → {NAME}_TIMEOUT error_code generation
        """
        start: float = time.monotonic()
        try:
            data: dict[str, object] = await self._execute_async(params)
            elapsed_ms: int = round((time.monotonic() - start) * 1000)
            return ToolResult(
                success=True,
                data=data,
                source=self.name,
                execution_time_ms=elapsed_ms,
            )
        except ConnectorHttpError as e:
            elapsed_ms = round((time.monotonic() - start) * 1000)
            return ToolResult(
                success=False,
                error_code=e.error_code,
                error_message=str(e),
                source=self.name,
                execution_time_ms=elapsed_ms,
            )
        except ConnectorTimeoutError as e:
            elapsed_ms = round((time.monotonic() - start) * 1000)
            return ToolResult(
                success=False,
                error_code=f"{self.name.upper()}_TIMEOUT",
                error_message=str(e),
                source=self.name,
                execution_time_ms=elapsed_ms,
            )

    # ── Schema generation ───────────────────────────────────────────────

    def get_tool_schema(self) -> dict[str, object]:
        """Return provider-agnostic tool metadata and parameter schema.

        Returns {name, description, parameters} where ``parameters`` is the
        JSON Schema for this tool's ``params_model`` (type, properties,
        required, and optional $defs).

        Provider-specific envelopes (e.g. OpenAI ``{"type": "function",
        "function": ...}``) are applied at the ToolRegistry or Executor
        layer — Tools are never coupled to a particular LLM provider.
        """
        raw_schema: dict[str, object] = cast(BaseModel, self.params_model).model_json_schema()
        parameters: dict[str, object] = {
            "type": raw_schema.get("type", "object"),
            "properties": raw_schema.get("properties", {}),
            "required": raw_schema.get("required", []),
        }

        # Forward any $defs so nested models resolve correctly.
        if "$defs" in raw_schema:
            parameters["$defs"] = raw_schema["$defs"]

        return {
            "name": self.name,
            "description": self.description,
            "parameters": parameters,
        }
