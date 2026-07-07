"""Chat router — exposes /chat, /chat/summary, /session, and /chats endpoints."""

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Response

from config import settings
from db.repositories.chat import IChatRepository, get_chat_repository
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
from routers.deps import (
    require_anon_id_cookie_async,
    require_valid_session_id_async,
    resolve_anon_id_async,
    validate_optional_session_id_async,
)
from services.chats.chat_service import (
    ChatTurnResult,
    IChatService,
    SessionRestoreResult,
    SummaryResult,
    get_chat_service,
)

router = APIRouter()
logger = structlog.get_logger()


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
    validated_session_id: Annotated[uuid.UUID | None, Depends(validate_optional_session_id_async)],
    resolved_anon_id: Annotated[uuid.UUID, Depends(resolve_anon_id_async)],
    chat_service: Annotated[IChatService, Depends(get_chat_service)],
) -> SuccessResponse[ChatResponse]:
    """Handle a single conversation turn and return the assistant reply.

    Args:
        request: Inbound payload containing session_id and user message.
        response: FastAPI Response object used to set the anon_id cookie.
        validated_session_id: Parsed session_id, validated by dependency.
        resolved_anon_id: Anonymous user identity resolved from HttpOnly cookie.
        chat_service: Chat orchestration service injected via FastAPI Depends
            (already wired to its own LLM client and chat repository).

    Returns:
        ChatResponse with reply, extracted fields, and optional routing.

    Raises:
        BadRequestError: When session_id is present but not a valid UUID string.
    """
    result: ChatTurnResult = await chat_service.process_turn_async(
        session_id=validated_session_id,
        message=request.message,
        anon_id=resolved_anon_id,
    )

    response.set_cookie(
        key="propertyai_anon_id",
        value=str(resolved_anon_id),
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
    session_id: Annotated[uuid.UUID, Depends(require_valid_session_id_async)],
    chat_service: Annotated[IChatService, Depends(get_chat_service)],
) -> SuccessResponse[SessionRestoreResponse]:
    """Return the conversation state for a session, with DB fallback when Redis has expired.

    Args:
        session_id: Parsed session_id, validated by dependency.
        chat_service: Chat orchestration service injected via FastAPI Depends
            (already wired to its own LLM client and chat repository).

    Returns:
        SessionRestoreResponse with state snapshot and optional welcome-back message.

    Raises:
        BadRequestError: When session_id is not a valid UUID string.
        SessionNotFoundError: When the session is absent from both Redis and DB.
        LLMServiceError: When the LLM call fails during DB restore (state not re-seeded).
    """
    result: SessionRestoreResult = await chat_service.restore_session_async(
        session_id=session_id,
    )

    return SuccessResponse[SessionRestoreResponse](
        data=SessionRestoreResponse(
            resume_message=result.resume_message,
            state=_snapshot_from_state(result.state),
            conversation_history=result.conversation_history,
        )
    )


@router.get("/chats", tags=["chat"])
async def list_chats_async(
    resolved_anon_id: Annotated[uuid.UUID, Depends(require_anon_id_cookie_async)],
    chat_repo: Annotated[IChatRepository, Depends(get_chat_repository)],
) -> SuccessResponse[list[ChatSessionDTO]]:
    """Return all chat sessions for an anonymous user, ordered newest first.

    Returns an empty list when the anon_id is valid but has no persisted sessions.
    Does not 404 on an unknown anon_id — returning an empty list avoids leaking
    information about whether a given anon_id has ever been seen.

    The anon_id is read from the propertyai_anon_id HttpOnly cookie; a missing or
    invalid cookie yields a 400 error without creating a new identity.

    Args:
        resolved_anon_id: Parsed UUID from HttpOnly cookie, validated by dependency.
        chat_repo: Chat repository injected via FastAPI Depends.

    Returns:
        List of ChatSessionDTO ordered by updated_at descending.

    Raises:
        BadRequestError: When the cookie is absent or its value is not a valid UUID.
    """
    sessions: list[ChatSessionDTO] = await chat_repo.list_chats_by_anon_async(resolved_anon_id)
    logger.info("list_chats_response", anon_id=str(resolved_anon_id), count=len(sessions))
    return SuccessResponse[list[ChatSessionDTO]](data=sessions)


@router.post("/chat/summary", tags=["chat"])
async def chat_summary_async(
    request: SummaryRequest,
    chat_service: Annotated[IChatService, Depends(get_chat_service)],
) -> SuccessResponse[SummaryResponse]:
    """Return a natural-language summary of all collected property requirements.

    Summary generation (all-None validation, prompt build, LLM call, UserNeeds
    assembly) lives in services.chats.chat_service.ChatService.generate_summary_async.

    Args:
        request: Inbound payload carrying the CollectedData to summarise.
        chat_service: Chat orchestration service injected via FastAPI Depends
            (already wired to its own LLM client).

    Returns:
        SummaryResponse with summary_text and the original structured data.

    Raises:
        SummaryValidationError: When all fields across all sub-models are None.
    """
    result: SummaryResult = await chat_service.generate_summary_async(
        collected_data=request.collected_data,
        session_id=request.session_id,
        initial_intent=request.initial_intent,
    )
    return SuccessResponse[SummaryResponse](
        data=SummaryResponse(summary_text=result.summary_text, structured=result.user_needs)
    )
