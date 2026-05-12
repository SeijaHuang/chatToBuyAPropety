"""Chat router — exposes /chat and /chat/summary endpoints for the conversation flow."""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends

from conversation.intent_router import classify_intent
from conversation.state_machine import merge_extracted_fields
from domain.borrowing_capacity import estimate_borrowing_capacity_async
from domain.budget_gap_detector import detect_budget_gap_async
from domain.llm_client import ILLMClient, OpenRouterClient
from domain.user_needs_builder import build_user_needs
from exceptions import SummaryValidationError
from models.chat import ChatRequest, ChatResponse
from models.conversation_state import ESubmodel
from models.summary import SummaryRequest, SummaryResponse
from prompts.system_prompt_builder import (
    build_extraction_prompt,
    build_question_prompt,
    build_summary_prompt,
)
from tools.extraction_schema import EXTRACT_REQUIREMENTS_TOOL

router = APIRouter()
logger = structlog.get_logger()

_default_llm_client: ILLMClient = OpenRouterClient()


@router.post("/chat")
async def chat_async(
    request: ChatRequest,
    llm_client: Annotated[ILLMClient, Depends(lambda: _default_llm_client)],
) -> ChatResponse:
    """Handle a single conversation turn and return the assistant reply.

    Processing order:
      1. Append user message to conversation history.
      2. Round 1 — Extraction: call LLM with extraction tool to pull structured fields.
      3. Merge extracted fields into state (advances module, recalculates completion).
      4. Round 2 — Question generation: call LLM plain completion with updated state.
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
    log = logger.bind(
        session_id=state.session_id,
        current_module=state.current_module,
    )
    log.info("chat_request_received", message_length=len(request.message))

    state.conversation_history.append({"role": "user", "content": request.message})

    extraction_prompt = build_extraction_prompt(state)
    extracted = await llm_client.chat_with_tools_async(
        extraction_prompt,
        state.conversation_history,
        [EXTRACT_REQUIREMENTS_TOOL],
    )
    log.info(
        "extraction_complete",
        extracted_field_count=len(extracted),
        extracted_fields=list(extracted.keys()),
    )

    merge_extracted_fields(state, extracted)
    log.info(
        "state_advanced",
        new_module=state.current_module,
        completion_status=state.completion_status.model_dump(),
    )

    if state.collected_data.m4.pre_tax_salary is not None:
        state.borrowing_capacity = await estimate_borrowing_capacity_async(state.collected_data.m4)

    m3 = state.collected_data.m3
    m4 = state.collected_data.m4
    gap_suburbs: list[str] = list(m3.preferred_suburbs or [])
    if not gap_suburbs and m3.commute_destination is not None:
        gap_suburbs = [m3.commute_destination]
    if m4.budget_max is not None and gap_suburbs:
        state.budget_gap = await detect_budget_gap_async(
            budget_max=m4.budget_max,
            property_type=state.collected_data.m1.property_type,
            min_bedrooms=state.collected_data.m1.min_bedrooms,
            suburbs=gap_suburbs,
        )

    question_prompt = build_question_prompt(state)
    reply = await llm_client.complete_async(question_prompt, request.message)

    state.conversation_history.append({"role": "assistant", "content": reply})

    routing = classify_intent(request.message, state)
    log.info("chat_response_ready", has_routing=routing is not None)

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
        logger.warning("summary_rejected_all_none")
        raise SummaryValidationError("No data collected — cannot generate summary.")

    logger.info("summary_request_received")
    system_prompt = build_summary_prompt(data)
    reply = await llm_client.complete_async(
        system_prompt, "Please generate the requirements summary."
    )
    logger.info("summary_generated", summary_length=len(reply))
    user_needs = build_user_needs(data, request.session_id, request.initial_intent)
    return SummaryResponse(summary_text=reply, structured=user_needs)
