"""Chat router — exposes /chat, /chat/summary, /session, and /chats endpoints."""

import json
from typing import Annotated
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Response
from pydantic import ValidationError

from config import settings
from conversation.intent_router import classify_intent
from conversation.state_machine import (
    get_current_module,
    merge_extracted_fields,
    recalculate_completion,
)
from db.repositories.chat import IChatRepository, get_chat_repository
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
    SessionRestoreResponse,
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
    build_session_restore_prompt,
    build_summary_prompt,
)
from redis_store.session_store import session_store
from routers.deps import require_anon_id_cookie_async, resolve_anon_id_async
from tools.extraction_schema import EXTRACT_REQUIREMENTS_TOOL

router = APIRouter()
logger = structlog.get_logger()

_default_llm_client: ILLMClient = OpenRouterClient()


@router.post("/chat", tags=["chat"])
async def chat_async(
    request: ChatRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    llm_client: Annotated[ILLMClient, Depends(lambda: _default_llm_client)],
    chat_repo: Annotated[IChatRepository, Depends(get_chat_repository)],
    resolved_anon_id: Annotated[str, Depends(resolve_anon_id_async)],
) -> SuccessResponse[ChatResponse]:
    """Handle a single conversation turn and return the assistant reply.

    State is loaded from Redis using the session_id in the request. When no
    session exists yet (first call), a fresh ConversationStateDTO is created
    automatically (PRD §21.3.1).

    Processing order:
      1. resolved_anon_id is injected by the Cookie dependency; always a valid DB-backed str.
      2. Load state from Redis; auto-create if absent.
      3. Append user message to conversation history.
      4. Round 1 — Extraction: call LLM with extraction tool to pull structured fields.
      5. Merge extracted fields into state (advances module, recalculates completion).
      6. Round 2 — Question generation: call LLM plain completion with updated state.
      7. Append assistant reply to conversation history.
      8. Persist updated state back to Redis.
      9. Classify intent for downstream routing.
      10. Schedule DB upsert via BackgroundTasks if this is a new session (first message)
          or if any module newly completed.
      11. Set HttpOnly cookie and return ChatResponse.

    Args:
        request: Inbound payload containing session_id and user message.
        response: FastAPI Response object used to set the anon_id cookie.
        background_tasks: FastAPI background task queue for async DB writes.
        llm_client: LLM client injected via FastAPI Depends (mockable in tests).
        chat_repo: Chat repository injected via FastAPI Depends.
        resolved_anon_id: Anonymous user identity resolved from HttpOnly cookie.

    Returns:
        ChatResponse with reply, extracted fields, and optional routing.
    """

    session_id: str = request.session_id if request.session_id else str(uuid4())
    _loaded: ConversationStateDTO | None = await session_store.load_session_async(session_id)
    is_new_session: bool = _loaded is None
    state: ConversationStateDTO = (
        _loaded if _loaded is not None else ConversationStateDTO(session_id=session_id)
    )

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
    if is_new_session or newly_completed:
        background_tasks.add_task(chat_repo.upsert_chat_snapshot_async, state, resolved_anon_id)
        log.info("db_upsert_scheduled", session_id=state.session_id)

    response.set_cookie(
        key="propertyai_anon_id",
        value=resolved_anon_id,
        httponly=True,
        samesite="strict",
        secure=settings.cookie_secure,
        path="/api/v1",
        max_age=settings.cookie_max_age,
    )
    return SuccessResponse[ChatResponse](
        data=ChatResponse(
            reply=reply,
            extracted=extracted,
            session_id=state.session_id,
            state=snapshot,
            routing=routing,
        )
    )


@router.get("/chat/{session_id}", tags=["chat"])
async def get_session_async(
    session_id: str,
    chat_repo: Annotated[IChatRepository, Depends(get_chat_repository)],
    llm_client: Annotated[ILLMClient, Depends(lambda: _default_llm_client)],
) -> SuccessResponse[SessionRestoreResponse]:
    """Return the conversation state for a session, with DB fallback when Redis has expired.

    Processing order:
      1. Validate session_id is a well-formed UUID.
      2. Try Redis — on hit return immediately with resume_message=None.
      3. On Redis miss, query the DB via get_chat_snapshot_async.
      4. If DB also misses, raise SessionNotFoundError.
      5. Reconstruct ConversationStateDTO from the DB row (no conversation_history).
      6. Re-derive completion_status and current_module from collected_data.
      7. Call LLM to generate a welcome-back message.
      8. Append the welcome message as the first assistant turn in conversation_history.
      9. Re-seed Redis so subsequent calls are cache-hits.
      10. Return SessionRestoreResponse with resume_message and state snapshot.

    Args:
        session_id: UUID v4 session identifier.
        chat_repo: Chat repository injected via FastAPI Depends.
        llm_client: LLM client injected via FastAPI Depends (mockable in tests).

    Returns:
        SessionRestoreResponse with state snapshot and optional welcome-back message.

    Raises:
        BadRequestError: When session_id is not a valid UUID string.
        SessionNotFoundError: When the session is absent from both Redis and DB.
        LLMServiceError: When the LLM call fails during DB restore (state not re-seeded).
    """
    try:
        UUID(session_id)
    except ValueError:
        raise BadRequestError(f"Invalid session_id: '{session_id}' is not a valid UUID.")

    redis_state: ConversationStateDTO | None = await session_store.load_session_async(session_id)
    if redis_state is not None:
        snapshot: ConversationSnapshotDTO = ConversationSnapshotDTO(
            session_id=redis_state.session_id,
            current_module=redis_state.current_module,
            status=redis_state.status,
            completion_status=redis_state.completion_status,
            collected_data=redis_state.collected_data,
            borrowing_capacity=redis_state.borrowing_capacity,
            budget_gap=redis_state.budget_gap,
        )
        return SuccessResponse[SessionRestoreResponse](
            data=SessionRestoreResponse(
                resume_message=None,
                state=snapshot,
                conversation_history=redis_state.conversation_history,
            )
        )

    log: structlog.BoundLogger = logger.bind(session_id=session_id)

    db_state: ConversationStateDTO | None = await chat_repo.get_chat_snapshot_async(session_id)
    if db_state is None:
        raise SessionNotFoundError(session_id)

    log.info("session_restore_from_db")

    db_state.completion_status = recalculate_completion(db_state.collected_data)
    db_state.current_module = get_current_module(db_state.completion_status)

    restore_prompt: str = build_session_restore_prompt(db_state)
    resume_message: str = await llm_client.complete_async(
        restore_prompt, "Please write a welcome-back message."
    )
    log.info("session_restore_message_generated")

    db_state.conversation_history.append({"role": "assistant", "content": resume_message})

    try:
        await session_store.save_session_async(db_state)
    except Exception:
        log.warning("redis_reseed_failed")

    db_snapshot: ConversationSnapshotDTO = ConversationSnapshotDTO(
        session_id=db_state.session_id,
        current_module=db_state.current_module,
        status=db_state.status,
        completion_status=db_state.completion_status,
        collected_data=db_state.collected_data,
        borrowing_capacity=db_state.borrowing_capacity,
        budget_gap=db_state.budget_gap,
    )
    return SuccessResponse[SessionRestoreResponse](
        data=SessionRestoreResponse(
            resume_message=resume_message,
            state=db_snapshot,
            conversation_history=[],
        )
    )


@router.get("/chats", tags=["chat"])
async def list_chats_async(
    resolved_anon_id: Annotated[str, Depends(require_anon_id_cookie_async)],
    chat_repo: Annotated[IChatRepository, Depends(get_chat_repository)],
) -> SuccessResponse[list[ChatSessionDTO]]:
    """Return all chat sessions for an anonymous user, ordered newest first.

    Returns an empty list when the anon_id is valid but has no persisted sessions.
    Does not 404 on an unknown anon_id — returning an empty list avoids leaking
    information about whether a given anon_id has ever been seen.

    The anon_id is read from the propertyai_anon_id HttpOnly cookie; a missing or
    invalid cookie yields a 400 error without creating a new identity.

    Args:
        resolved_anon_id: UUID string from HttpOnly cookie, validated by dependency.
        chat_repo: Chat repository injected via FastAPI Depends.

    Returns:
        List of ChatSessionDTO ordered by updated_at descending.

    Raises:
        BadRequestError: When the cookie is absent or its value is not a valid UUID.
    """
    sessions: list[ChatSessionDTO] = await chat_repo.list_chats_by_anon_async(resolved_anon_id)
    logger.info("list_chats_response", anon_id=resolved_anon_id, count=len(sessions))
    return SuccessResponse[list[ChatSessionDTO]](data=sessions)


@router.post("/chat/summary", tags=["chat"])
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
