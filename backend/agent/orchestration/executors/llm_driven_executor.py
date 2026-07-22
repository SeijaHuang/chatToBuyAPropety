"""LLM-driven execution for open-ended queries (PRD §S4.4).

Exposes available Tools to the LLM; the LLM decides which Tools
to call, with what parameters, and when to stop.
"""

from typing import Annotated, Any, cast

import structlog
from fastapi import Depends
from pydantic import BaseModel

from agent.orchestration.executors.base import IExecutor
from agent.shared.context import ExecutionContext
from agent.tool_registry.registry import IToolRegistry, get_tool_registry
from agent.tools.base import BaseTool
from agent.tools.result import ToolResult
from domain.llm_client import ILLMClient, get_llm_client
from models.shared.execution_response import EExecutionStatus, ExecutionResponse

logger = structlog.get_logger()


class LLMDrivenExecutor(IExecutor):
    """LLM-driven execution for open-ended queries.

    Exposes available Tools to the LLM; the LLM decides which Tools
    to call, with what parameters, and when to stop.

    Known limitations (prototype phase):
      - ILLMClient.chat_with_tools_async returns single tool call args only.
        Multi-tool-call responses and tool-result round-trips require an
        ILLMClient extension tracked in a follow-up task.
        See PRD §11 I4.
    """

    def __init__(
        self,
        llm: ILLMClient,
        registry: IToolRegistry,
        max_rounds: int = 5,
        timeout_secs: float = 30.0,
    ) -> None:
        """Initialise with LLM client, tool registry, and loop limits.

        Args:
            llm: LLM client implementing ILLMClient Protocol.
            registry: Tool registry implementing IToolRegistry Protocol.
            max_rounds: Maximum number of tool-calling rounds before returning PARTIAL.
            timeout_secs: Reserved for future timeout enforcement (not wired yet).
        """
        self._llm: ILLMClient = llm
        self._registry: IToolRegistry = registry
        self._max_rounds: int = max_rounds
        self._timeout_secs: float = timeout_secs

    async def execute_async(self, context: ExecutionContext) -> ExecutionResponse:
        """Run the LLM + tool-calling loop.

        Args:
            context: Immutable execution context from ContextResolver.

        Returns:
            ExecutionResponse with the final result.
        """
        log: structlog.BoundLogger = logger.bind(
            session_id=context.session_id, intent=context.intent
        )

        messages: list[dict[str, object]] = [self._build_system_message(context)]
        tool_schemas: list[dict[str, object]] = self._registry.get_openai_tool_schemas()

        for round_idx in range(self._max_rounds):
            log.info("llm_round_start", round=round_idx)

            # TODO(agent): Replace with multi-round ILLMClient method once available.
            # The current chat_with_tools_async returns parsed tool-call arguments
            # (or {}) — it does not return content + tool_calls[] + tool_call_id
            # needed for full multi-round conversation.
            response: dict[str, object] = await self._llm.chat_with_tools_async(
                system_prompt="",
                messages=messages,
                tools=tool_schemas,
            )

            # No tool call — LLM chose to answer directly
            if not response:
                return ExecutionResponse(
                    status=EExecutionStatus.SUCCESS,
                    data={"reply": "LLM returned without tool calls (prototype path)"},
                )

            # Tool call returned — execute and feed result back
            tool_name: str = str(response.get("name", ""))
            tool: BaseTool[Any] = self._registry.get(tool_name)
            params_model: type[BaseModel] = cast(type[BaseModel], tool.params_model)
            params: BaseModel = params_model.model_validate(response)
            result: ToolResult = await tool.run_async(params)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": f"call_{round_idx}",
                    "content": result.model_dump_json(),
                }
            )

        return ExecutionResponse(
            status=EExecutionStatus.PARTIAL,
            data={"reply": "查询超时。请尝试更具体的问题。"},
        )

    def _build_system_message(self, context: ExecutionContext) -> dict[str, object]:
        """Serialize ExecutionContext into the LLM system prompt.

        Args:
            context: Execution context with user preferences and location data.

        Returns:
            A dict suitable for use as a system message in the LLM conversation.
        """
        parts: list[str] = [
            "You are a property buying assistant with access to real-time data tools.",
            "Use the tools available to you to answer the user's question.",
            f"Session ID: {context.session_id}",
            f"User preferences: {context.user_needs.model_dump_json()}",
        ]
        if context.property_lat is not None and context.property_lng is not None:
            parts.append(
                f"Property location: lat={context.property_lat}, lng={context.property_lng}"
            )
        if context.target_entity_label:
            parts.append(f"Target: {context.target_entity_label}")

        return {"role": "system", "content": "\n\n".join(parts)}


def get_llm_driven_executor(
    llm: Annotated[ILLMClient, Depends(get_llm_client)],
    registry: Annotated[IToolRegistry, Depends(get_tool_registry)],
) -> IExecutor:
    """FastAPI dependency — returns an LLMDrivenExecutor wired to its dependencies."""
    return LLMDrivenExecutor(llm=llm, registry=registry)
