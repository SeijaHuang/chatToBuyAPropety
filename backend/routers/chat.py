"""Chat router — exposes /chat, /chat/summary, /session, and /chats endpoints."""

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Response

from config import settings
from db.repositories.chat import IChatRepository, get_chat_repository
from domain.llm_client import ILLMClient, OpenRouterClient
from exceptions import BadRequestError, SessionNotFoundError
from models.base import SuccessResponse
from models.chat import (
    ChatRequest,
    ChatResponse,
    ChatSessionDTO,
    ConversationSnapshotDTO,
    SessionRestoreResponse,
)
from models.conversation_state import ConversationStateDTO
from models.summary import SummaryRequest, SummaryResponse
from routers.deps import require_anon_id_cookie_async, resolve_anon_id_async
from services.chats.chat_service import (
    ChatTurnResult,
    IChatService,
    SessionRestoreResult,
    SummaryResult,
    get_chat_service,
)

router = APIRouter()
logger = structlog.get_logger()

_default_llm_client: ILLMClient = OpenRouterClient()


def _snapshot_from_state(state: ConversationStateDTO) -> ConversationSnapshotDTO:
    """Build the response-shaping snapshot DTO from a full ConversationStateDTO."""
    return ConversationSnapshotDTO(
        session_id=state.session_id,
        current_module=state.current_module,
        status=state.status,
        completion_status=state.completion_status,
        collected_data=state.collected_data,
        borrowing_capacity=state.borrowing_capacity,
        budget_gap=state.budget_gap,
    )


@router.post("/chat", tags=["chat"])
async def chat_async(
    request: ChatRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    llm_client: Annotated[ILLMClient, Depends(lambda: _default_llm_client)],
    chat_repo: Annotated[IChatRepository, Depends(get_chat_repository)],
    resolved_anon_id: Annotated[str, Depends(resolve_anon_id_async)],
    chat_service: Annotated[IChatService, Depends(get_chat_service)],
) -> SuccessResponse[ChatResponse]:
    """Handle a single conversation turn and return the assistant reply.

    All turn-processing logic (session load/create, both LLM rounds, field
    merging, financial recompute, intent classification) lives in
    services.chats.chat_service.ChatService. This handler only resolves
    dependencies, schedules the background DB upsert, sets the identity
    cookie, and shapes the HTTP response.

    Args:
        request: Inbound payload containing session_id and user message.
        response: FastAPI Response object used to set the anon_id cookie.
        background_tasks: FastAPI background task queue for async DB writes.
        llm_client: LLM client injected via FastAPI Depends (mockable in tests).
        chat_repo: Chat repository injected via FastAPI Depends.
        resolved_anon_id: Anonymous user identity resolved from HttpOnly cookie.
        chat_service: Chat orchestration service injected via FastAPI Depends.

    Returns:
        ChatResponse with reply, extracted fields, and optional routing.
    """
    result: ChatTurnResult = await chat_service.process_turn_async(
        session_id=request.session_id,
        message=request.message,
        llm_client=llm_client,
    )

    if result.should_persist:
        background_tasks.add_task(
            chat_repo.upsert_chat_snapshot_async, result.state, resolved_anon_id
        )

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
            reply=result.reply,
            extracted=result.extracted,
            session_id=result.state.session_id,
            state=_snapshot_from_state(result.state),
            routing=result.routing,
        )
    )


@router.get("/chat/{session_id}", tags=["chat"])
async def get_session_async(
    session_id: str,
    llm_client: Annotated[ILLMClient, Depends(lambda: _default_llm_client)],
    chat_repo: Annotated[IChatRepository, Depends(get_chat_repository)],
    chat_service: Annotated[IChatService, Depends(get_chat_service)],
) -> SuccessResponse[SessionRestoreResponse]:
    """Return the conversation state for a session, with DB fallback when Redis has expired.

    Session-resolution strategy (Redis hit, Postgres fallback with an
    LLM-generated welcome message, or neither) lives entirely in
    services.chats.chat_service.ChatService.restore_session_async. This handler
    only validates the path parameter and shapes the HTTP response.

    Args:
        session_id: UUID v4 session identifier.
        llm_client: LLM client injected via FastAPI Depends (mockable in tests).
        chat_repo: Chat repository injected via FastAPI Depends.
        chat_service: Chat orchestration service injected via FastAPI Depends.

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

    result: SessionRestoreResult | None = await chat_service.restore_session_async(
        session_id=session_id,
        chat_repo=chat_repo,
        llm_client=llm_client,
    )
    if result is None:
        raise SessionNotFoundError(session_id)

    return SuccessResponse[SessionRestoreResponse](
        data=SessionRestoreResponse(
            resume_message=result.resume_message,
            state=_snapshot_from_state(result.state),
            conversation_history=result.conversation_history,
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
    chat_service: Annotated[IChatService, Depends(get_chat_service)],
) -> SuccessResponse[SummaryResponse]:
    """Return a natural-language summary of all collected property requirements.

    Summary generation (all-None validation, prompt build, LLM call, UserNeeds
    assembly) lives in services.chats.chat_service.ChatService.generate_summary_async.

    Args:
        request: Inbound payload carrying the CollectedData to summarise.
        llm_client: LLM client injected via FastAPI Depends (mockable in tests).
        chat_service: Chat orchestration service injected via FastAPI Depends.

    Returns:
        SummaryResponse with summary_text and the original structured data.

    Raises:
        SummaryValidationError: When all fields across all sub-models are None.
    """
    result: SummaryResult = await chat_service.generate_summary_async(
        collected_data=request.collected_data,
        session_id=request.session_id,
        initial_intent=request.initial_intent,
        llm_client=llm_client,
    )
    return SuccessResponse[SummaryResponse](
        data=SummaryResponse(summary_text=result.summary_text, structured=result.user_needs)
    )
