"""Chat router — exposes /chat, /chat/summary, /session, and /chats endpoints."""

import json
import uuid
from typing import Annotated
from uuid import uuid4

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import ValidationError

from conversation.intent_router import classify_intent
from conversation.state_machine import merge_extracted_fields
from db.repositories.chat import SqlAlchemyChatRepository, get_chat_repository
from db.repositories.user import SqlAlchemyUserRepository, get_user_repository
from domain.borrowing_capacity import estimate_borrowing_capacity_async
from domain.budget_gap_detector import detect_budget_gap_async
from domain.llm_client import ILLMClient, OpenRouterClient
from domain.user_needs_builder import build_user_needs
from exceptions import BadRequestError, SessionNotFoundError, SummaryValidationError
from models.base import SuccessResponse
from models.chat import (
    ChatRequest,
    ChatResponse,
    ChatSessionDTO,
    ConversationSnapshotDTO,
    RoutingPayload,
)
from models.conversation_state import (
    CollectedData,
    CompletionStatus,
    ConversationStateDTO,
    ESubmodel,
    EUserIntent,
    M3SuburbPreference,
    M4Budget,
)
from models.summary import SummaryRequest, SummaryResponse
from models.user_needs import UserNeeds
from prompts.system_prompt_builder import (
    build_extraction_prompt,
    build_question_prompt,
    build_summary_prompt,
)
from redis_store.session_store import session_store
from tools.extraction_schema import EXTRACT_REQUIREMENTS_TOOL

router = APIRouter()
logger = structlog.get_logger()

_default_llm_client: ILLMClient = OpenRouterClient()


@router.post("/chat")
async def chat_async(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    llm_client: Annotated[ILLMClient, Depends(lambda: _default_llm_client)],
    chat_repo: Annotated[SqlAlchemyChatRepository, Depends(get_chat_repository)],
    anon_repo: Annotated[SqlAlchemyUserRepository, Depends(get_user_repository)],
) -> SuccessResponse[ChatResponse]:
    """Handle a single conversation turn and return the assistant reply.

    State is loaded from Redis using the session_id in the request. When no
    session exists yet (first call), a fresh ConversationStateDTO is created
    automatically (PRD §21.3.1).

    Processing order:
      1. Resolve anon_id — find existing or create new anonymous user identity.
         resolved_anon_id is always a valid DB-backed str; request.anon_id may be None.
      2. Load state from Redis; auto-create if absent.
      3. Append user message to conversation history.
      4. Round 1 — Extraction: call LLM with extraction tool to pull structured fields.
      5. Merge extracted fields into state (advances module, recalculates completion).
      6. Round 2 — Question generation: call LLM plain completion with updated state.
      7. Append assistant reply to conversation history.
      8. Persist updated state back to Redis.
      9. Classify intent for downstream routing.
      10. Schedule DB upsert via BackgroundTasks if any module newly completed.
      11. Return ChatResponse (including resolved anon_id for frontend localStorage).

    Args:
        request: Inbound payload containing session_id, anon_id, and user message.
        background_tasks: FastAPI background task queue for async DB writes.
        llm_client: LLM client injected via FastAPI Depends (mockable in tests).
        chat_repo: Chat repository injected via FastAPI Depends.
        anon_repo: Anonymous user repository injected via FastAPI Depends.

    Returns:
        ChatResponse with reply, extracted fields, resolved anon_id, and optional routing.
    """
    # resolved_anon_id is guaranteed to be a non-None str backed by an existing DB row,
    # satisfying both ChatResponse.anon_id: str and the chats.anon_id FK constraint.
    resolved_anon_id: str = await anon_repo.get_or_create_async(request.anon_id)

    session_id: str = request.session_id if request.session_id else str(uuid4())
    state: ConversationStateDTO | None = await session_store.load_session_async(session_id)
    if state is None:
        state = ConversationStateDTO(session_id=session_id)

    log: structlog.BoundLogger = logger.bind(
        session_id=state.session_id,
        current_module=state.current_module,
    )
    log.info("chat_request_received", message_length=len(request.message))

    state.conversation_history.append({"role": "user", "content": request.message})

    # Snapshot completion before extraction to detect newly completed modules
    prev_completion: CompletionStatus = state.completion_status.model_copy()

    extraction_prompt: str = build_extraction_prompt(state)
    extracted: dict[str, object]
    try:
        extracted = await llm_client.chat_with_tools_async(
            extraction_prompt,
            state.conversation_history,
            [EXTRACT_REQUIREMENTS_TOOL],
        )
        merge_extracted_fields(state, extracted)
    except (json.JSONDecodeError, ValidationError) as exc:
        log.warning("tool_call_parse_failed", error=str(exc))
        extracted = {}

    log.info(
        "extraction_complete",
        extracted_field_count=len(extracted),
        extracted_fields=list(extracted.keys()),
    )
    log.info(
        "state_advanced",
        new_module=state.current_module,
        completion_status=state.completion_status.model_dump(),
    )

    if state.collected_data.m4.pre_tax_salary is not None:
        state.borrowing_capacity = await estimate_borrowing_capacity_async(state.collected_data.m4)

    m3: M3SuburbPreference = state.collected_data.m3
    m4: M4Budget = state.collected_data.m4
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

    question_prompt: str = build_question_prompt(state)
    reply: str = await llm_client.complete_async(question_prompt, request.message)

    state.conversation_history.append({"role": "assistant", "content": reply})

    await session_store.save_session_async(state)

    user_needs: UserNeeds = build_user_needs(state.collected_data, state.session_id)
    routing: RoutingPayload | None = classify_intent(request.message, state, user_needs)
    log.info("chat_response_ready", has_routing=routing is not None)

    snapshot: ConversationSnapshotDTO = ConversationSnapshotDTO(
        session_id=state.session_id,
        current_module=state.current_module,
        status=state.status,
        completion_status=state.completion_status,
        collected_data=state.collected_data,
        borrowing_capacity=state.borrowing_capacity,
        budget_gap=state.budget_gap,
    )

    # Write initial_intent when M1 first completes this turn
    m1_just_completed: bool = state.completion_status.M1 and not prev_completion.M1
    if m1_just_completed and state.initial_intent is None:
        state.initial_intent = (
            routing.intent if routing is not None else EUserIntent.OPEN_ENDED_QUERY
        )

    # Trigger DB upsert in background whenever any module newly completes
    newly_completed: bool = any(
        state.completion_status[m] and not prev_completion[m] for m in ESubmodel
    )
    if newly_completed:
        background_tasks.add_task(chat_repo.upsert_chat_snapshot_async, state, resolved_anon_id)
        log.info("db_upsert_scheduled", session_id=state.session_id)

    return SuccessResponse[ChatResponse](
        data=ChatResponse(
            reply=reply,
            extracted=extracted,
            session_id=state.session_id,
            anon_id=resolved_anon_id,
            state=snapshot,
            routing=routing,
        )
    )


@router.get("/chat/{session_id}")
async def get_session_async(
    session_id: str,
) -> SuccessResponse[ConversationStateDTO]:
    """Return the current conversation state for a session.

    Args:
        session_id: UUID v4 session identifier.

    Returns:
        The stored ConversationStateDTO wrapped in SuccessResponse.

    Raises:
        SessionNotFoundError: When the session is absent or has expired from Redis.
    """
    state: ConversationStateDTO | None = await session_store.load_session_async(session_id)
    if state is None:
        raise SessionNotFoundError(session_id)
    return SuccessResponse[ConversationStateDTO](data=state)


@router.get("/chats")
async def list_chats_async(
    anon_id: Annotated[str, Query(description="Anonymous user UUID from localStorage")],
    chat_repo: Annotated[SqlAlchemyChatRepository, Depends(get_chat_repository)],
) -> SuccessResponse[list[ChatSessionDTO]]:
    """Return all chat sessions for an anonymous user, ordered newest first.

    Returns an empty list when the anon_id is valid but has no persisted sessions.
    Does not 404 on an unknown anon_id — returning an empty list avoids leaking
    information about whether a given anon_id has ever been seen.

    Args:
        anon_id: UUID string identifying the anonymous user (from localStorage).
        chat_repo: Chat repository injected via FastAPI Depends.

    Returns:
        List of ChatSessionDTO ordered by updated_at descending.

    Raises:
        BadRequestError: When anon_id is not a valid UUID string.
    """
    try:
        uuid.UUID(anon_id)
    except ValueError:
        raise BadRequestError(f"Invalid anon_id: '{anon_id}' is not a valid UUID.")

    sessions: list[ChatSessionDTO] = await chat_repo.list_chats_by_anon_async(anon_id)
    logger.info("list_chats_response", anon_id=anon_id, count=len(sessions))
    return SuccessResponse[list[ChatSessionDTO]](data=sessions)


@router.post("/chat/summary")
async def chat_summary_async(
    request: SummaryRequest,
    llm_client: Annotated[ILLMClient, Depends(lambda: _default_llm_client)],
) -> SuccessResponse[SummaryResponse]:
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
    data: CollectedData = request.collected_data
    all_none: bool = all(
        value is None
        for submodel in ESubmodel
        for value in getattr(data, submodel).model_dump().values()
    )
    if all_none:
        logger.warning("summary_rejected_all_none")
        raise SummaryValidationError("No data collected — cannot generate summary.")

    logger.info("summary_request_received")
    system_prompt: str = build_summary_prompt(data)
    reply: str = await llm_client.complete_async(
        system_prompt, "Please generate the requirements summary."
    )
    logger.info("summary_generated", summary_length=len(reply))
    user_needs: UserNeeds = build_user_needs(data, request.session_id, request.initial_intent)
    return SuccessResponse[SummaryResponse](
        data=SummaryResponse(summary_text=reply, structured=user_needs)
    )
