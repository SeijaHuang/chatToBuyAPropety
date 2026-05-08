"""OpenRouter API wrapper — provides a typed async interface for all LLM calls."""

import json
from typing import Any, Protocol

import openai
from openai import AsyncOpenAI

from config import settings
from exceptions import LLMServiceError


class ILLMClient(Protocol):
    """Protocol contract for LLM client implementations."""

    async def chat_with_tools_async(
        self,
        system_prompt: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
    ) -> tuple[str, dict[str, object]]:
        """Call the LLM with tool support.

        Args:
            system_prompt: System prompt prepended internally; must not appear in messages.
            messages: Conversation history without the system message.
            tools: OpenAI-format tool definitions.

        Returns:
            Tuple of (assistant_reply_text, extracted_fields_dict).
            extracted_fields_dict is empty when no tool call is returned.
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
            # base_url=settings.llm_base_url,
        )

    async def chat_with_tools_async(
        self,
        system_prompt: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
    ) -> tuple[str, dict[str, object]]:
        """Send a chat request with tool support and return the reply and extracted fields.

        Prepends the system prompt as the first message internally.
        Strips control keys (module_complete, next_question, user_intent) from the
        returned extracted dict so callers only receive business fields.

        Args:
            system_prompt: The system prompt to prepend.
            messages: Conversation history (no system message).
            tools: OpenAI-format tool definitions.

        Returns:
            Tuple of (assistant_reply_text, extracted_fields_dict).

        Raises:
            LLMServiceError: When the OpenRouter API call fails.
        """
        full_messages: list[Any] = [{"role": "system", "content": system_prompt}, *messages]
        try:
            response = await self._client.chat.completions.create(  # type: ignore[call-overload]
                model=settings.model_strong,
                temperature=0.7,
                max_tokens=1000,
                tools=tools,
                tool_choice="auto",
                messages=full_messages,
            )
        except openai.APIError as exc:
            raise LLMServiceError(f"OpenRouter call failed: {exc}") from exc

        choice = response.choices[0]
        tool_calls = choice.message.tool_calls
        if not tool_calls:
            return choice.message.content or "", {}

        raw: dict[str, object] = json.loads(tool_calls[0].function.arguments)
        reply: str = str(raw.pop("next_question", ""))
        raw.pop("module_complete", None)
        raw.pop("user_intent", None)
        return reply, raw

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
        try:
            response = await self._client.chat.completions.create(
                model=settings.model_strong,
                temperature=0.7,
                max_tokens=1000,
                messages=full_messages,
            )
        except openai.APIError as exc:
            raise LLMServiceError(f"OpenRouter call failed: {exc}") from exc

        return response.choices[0].message.content or ""
