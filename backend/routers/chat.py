"""Chat router — exposes /chat and /chat/summary endpoints for the conversation flow."""

from typing import Annotated

from fastapi import APIRouter, Depends

from conversation.intent_router import classify_intent
from conversation.state_machine import merge_extracted_fields
from exceptions import SummaryValidationError
from models.schemas import ChatRequest, ChatResponse, ESubmodel, SummaryRequest, SummaryResponse
from prompts.system_prompt_builder import build_summary_prompt, build_system_prompt
from services.llm_client import ILLMClient, OpenRouterClient
from tools.extraction_schema import EXTRACT_REQUIREMENTS_TOOL

router = APIRouter()

_default_llm_client: ILLMClient = OpenRouterClient()


@router.post("/chat")
async def chat_async(
    request: ChatRequest,
    llm_client: Annotated[ILLMClient, Depends(lambda: _default_llm_client)],
) -> ChatResponse:
    """Handle a single conversation turn and return the assistant reply.

    Processing order:
      1. Append user message to conversation history.
      2. Build the module-specific system prompt.
      3. Call the LLM with the extraction tool.
      4. Merge extracted fields into state (also advances module and recalculates completion).
      5. Append assistant reply to conversation history.
      6. Classify intent for downstream routing.
      7. Return ChatResponse.

    Args:
        request: Inbound chat payload containing the user message and current state.
        llm_client: LLM client injected via FastAPI Depends (mockable in tests).

    Returns:
        ChatResponse with reply, extracted fields, updated state, and optional routing.
    """
    state = request.state
    state.conversation_history.append({"role": "user", "content": request.message})

    system_prompt = build_system_prompt(state)
    reply, extracted = await llm_client.chat_with_tools_async(
        system_prompt,
        state.conversation_history,
        [EXTRACT_REQUIREMENTS_TOOL],
    )

    merge_extracted_fields(state, extracted)

    state.conversation_history.append({"role": "assistant", "content": reply})

    routing = classify_intent(request.message, state)

    return ChatResponse(
        reply=reply,
        extracted=extracted,
        updated_state=state,
        routing=routing,
    )


@router.post("/chat/summary")
async def chat_summary_async(
    request: SummaryRequest,
    llm_client: Annotated[ILLMClient, Depends(lambda: _default_llm_client)],
) -> SummaryResponse:
    """Return a natural-language summary of all collected property requirements.

    Processing order:
      1. Raise SummaryValidationError when every field across all sub-models is None.
      2. Build the summary system prompt from the collected data.
      3. Call the LLM for a plain completion.
      4. Return SummaryResponse with the generated text and the unchanged structured data.

    Args:
        request: Inbound payload carrying the CollectedData to summarise.
        llm_client: LLM client injected via FastAPI Depends (mockable in tests).

    Returns:
        SummaryResponse with summary_text and the original structured data.

    Raises:
        SummaryValidationError: When all fields across all sub-models are None.
    """
    data = request.collected_data
    all_none = all(
        value is None
        for submodel in ESubmodel
        for value in getattr(data, submodel).model_dump().values()
    )
    if all_none:
        raise SummaryValidationError("No data collected — cannot generate summary.")

    system_prompt = build_summary_prompt(data)
    reply = await llm_client.complete_async(
        system_prompt, "Please generate the requirements summary."
    )
    return SummaryResponse(summary_text=reply, structured=data)
