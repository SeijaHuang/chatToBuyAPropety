"""OpenRouter API wrapper — provides a typed async interface for all LLM calls."""

import json
from typing import Any, Protocol

import structlog
from openai import AsyncOpenAI
from openai.types import CompletionUsage
from openai.types.chat import ChatCompletionMessageToolCall

from config import settings
from exceptions import LLMServiceError

logger = structlog.get_logger()


class ILLMClient(Protocol):
    """Protocol contract for LLM client implementations."""

    async def chat_with_tools_async(
        self,
        system_prompt: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
    ) -> dict[str, object]:
        """Call the LLM with tool support and return extracted business fields.

        Args:
            system_prompt: System prompt prepended internally; must not appear in messages.
            messages: Conversation history without the system message.
            tools: OpenAI-format tool definitions.

        Returns:
            Extracted business fields dict; empty dict when no tool call is returned.
        """
        ...

    async def complete_async(
        self,
        system_prompt: str,
        user_message: str,
    ) -> str:
        """Call the LLM for a plain completion (no tool calling).

        Args:
            system_prompt: System prompt for the completion.
            user_message: The user-turn message to complete.

        Returns:
            The assistant reply as a plain string.
        """
        ...


class OpenRouterClient(ILLMClient):
    """Async OpenRouter client backed by the OpenAI SDK."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.llm_base_url,
        )

    async def chat_with_tools_async(
        self,
        system_prompt: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
    ) -> dict[str, object]:
        """Send a chat request with tool support and return extracted business fields.

        Prepends the system prompt as the first message internally.

        Args:
            system_prompt: The system prompt to prepend.
            messages: Conversation history (no system message).
            tools: OpenAI-format tool definitions.

        Returns:
            Extracted business fields dict; empty dict when no tool call is returned.

        Raises:
            LLMServiceError: When the OpenRouter API call fails.
        """
        full_messages: list[Any] = [{"role": "system", "content": system_prompt}, *messages]
        log: structlog.BoundLogger = logger.bind(
            model=settings.model_strong, llm_method="chat_with_tools_async"
        )
        log.info("llm_call_start", message_count=len(full_messages), tool_count=len(tools))
        try:
            response = await self._client.chat.completions.create(  # type: ignore[call-overload]
                model=settings.model_strong,
                temperature=0.7,
                max_tokens=1000,
                tools=tools,
                tool_choice="auto",
                messages=full_messages,
            )
        except Exception as exc:
            log.error(
                "llm_call_failed",
                error=str(exc),
                status_code=getattr(exc, "status_code", None),
            )
            raise LLMServiceError(
                f"OpenRouter call failed: {exc}",
                details={
                    "model": settings.model_strong,
                    "llm_method": "chat_with_tools_async",
                    "status_code": getattr(exc, "status_code", None),
                    "provider_error": str(exc),
                },
            ) from exc

        usage: CompletionUsage | None = response.usage
        log.info(
            "llm_call_complete",
            has_tool_call=bool(response.choices[0].message.tool_calls),
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
        )

        tool_calls: list[ChatCompletionMessageToolCall] | None = response.choices[
            0
        ].message.tool_calls
        if not tool_calls:
            return {}

        raw: dict[str, object] = json.loads(tool_calls[0].function.arguments)
        return raw

    async def complete_async(
        self,
        system_prompt: str,
        user_message: str,
    ) -> str:
        """Call the LLM for a plain text completion with no tool calling.

        Args:
            system_prompt: System prompt for the completion.
            user_message: The user-turn message to complete.

        Returns:
            The assistant reply as a plain string.

        Raises:
            LLMServiceError: When the OpenRouter API call fails.
        """
        full_messages: list[Any] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        log: structlog.BoundLogger = logger.bind(
            model=settings.model_strong, llm_method="complete_async"
        )
        log.info("llm_call_start", message_count=len(full_messages))
        try:
            response = await self._client.chat.completions.create(
                model=settings.model_strong,
                temperature=0.7,
                max_tokens=1000,
                messages=full_messages,
            )
        except Exception as exc:
            log.error(
                "llm_call_failed",
                error=str(exc),
                status_code=getattr(exc, "status_code", None),
            )
            raise LLMServiceError(
                f"OpenRouter call failed: {exc}",
                details={
                    "model": settings.model_strong,
                    "llm_method": "complete_async",
                    "status_code": getattr(exc, "status_code", None),
                    "provider_error": str(exc),
                },
            ) from exc

        usage: CompletionUsage | None = response.usage
        log.info(
            "llm_call_complete",
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
        )
        return response.choices[0].message.content or ""


llm_client: OpenRouterClient = OpenRouterClient()
