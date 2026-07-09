"""Chat turn orchestration — the process-flow layer behind the chat endpoints.

Routers only resolve dependencies and shape HTTP responses; every multi-step
orchestration decision (session load/create, LLM rounds, field merging, financial
recompute, intent classification, session-restore strategy, summary generation)
lives here. This module sequences calls into conversation/ (state rules),
domain/ (pure business calculations, LLM gateway), and the repository/session-store
layer — it owns no business rule of its own.
"""

import json
from typing import Annotated, Protocol
from uuid import uuid4

import structlog
from fastapi import Depends
from pydantic import ValidationError

from conversation.intent_router import classify_intent
from conversation.state_machine import (
    get_current_module,
    merge_extracted_fields,
    recalculate_completion,
)
from db.repositories.chat import IChatRepository, get_chat_repository
from domain.borrowing_capacity import estimate_borrowing_capacity_async
from domain.budget_gap_detector import detect_budget_gap_async
from domain.llm_client import ILLMClient
from domain.llm_client import llm_client as _default_llm_client
from domain.user_needs_builder import build_user_needs
from exceptions import SessionNotFoundError, SummaryValidationError
from models.commands.get_chat import RestoreChatSessionCommand
from models.commands.get_chats import ListChatSessionsCommand
from models.commands.post_chat import ProcessChatTurnCommand
from models.commands.post_chat_summary import GenerateChatSummaryCommand
from models.dto.get_chat import ChatSessionRestoreDTO
from models.dto.get_chats import ChatSessionDTO
from models.dto.post_chat import ChatTurnDTO
from models.dto.post_chat_summary import ChatSummaryDTO
from models.shared.conversation_state import ConversationStateDTO
from models.shared.enums import ESubmodel, EUserIntent
from models.shared.submodels import CompletionStatus, M3SuburbPreference, M4Budget
from models.shared.user_needs import UserNeeds
from prompts.system_prompt_builder import (
    build_extraction_prompt,
    build_question_prompt,
    build_session_restore_prompt,
    build_summary_prompt,
)
from redis_store.session_store import ISessionStore
from redis_store.session_store import session_store as _default_session_store
from tools.extraction_schema import EXTRACT_REQUIREMENTS_TOOL

logger = structlog.get_logger()


class IChatService(Protocol):
    """Process-orchestration contract behind the chat endpoints."""

    async def process_turn_async(self, command: ProcessChatTurnCommand) -> ChatTurnDTO:
        """Process one conversation turn end to end.

        Args:
            command: Session id (or None for a new session), message, and anon_id.

        Returns:
            ChatTurnDTO describing the reply, updated state, and whether a
            Postgres upsert was performed this turn.
        """
        ...

    async def restore_session_async(
        self, command: RestoreChatSessionCommand
    ) -> ChatSessionRestoreDTO:
        """Resolve session state from Redis, falling back to Postgres on a miss.

        Args:
            command: Session identifier, already validated by the caller.

        Returns:
            ChatSessionRestoreDTO on a Redis or Postgres hit.

        Raises:
            SessionNotFoundError: When neither store has the session.
        """
        ...

    async def generate_summary_async(self, command: GenerateChatSummaryCommand) -> ChatSummaryDTO:
        """Generate a natural-language requirements summary.

        Args:
            command: Collected data, session id, and initial intent to summarise.

        Returns:
            ChatSummaryDTO with the generated text and UserNeeds snapshot.

        Raises:
            SummaryValidationError: When every field across all sub-models is None.
        """
        ...

    async def list_chats_async(self, command: ListChatSessionsCommand) -> list[ChatSessionDTO]:
        """Return all chat sessions for an anonymous user, ordered newest first.

        Args:
            command: Anonymous user identity resolved from the HttpOnly cookie.

        Returns:
            List of ChatSessionDTO ordered by updated_at descending.
        """
        ...


class ChatService(IChatService):
    """Default IChatService implementation, backed by the Redis session store.

    chat_repo has no import-time default because it wraps a session factory that
    only exists after FastAPI lifespan startup — callers must always supply it.
    """

    def __init__(
        self,
        chat_repo: IChatRepository,
        session_store: ISessionStore = _default_session_store,
        llm_client: ILLMClient = _default_llm_client,
    ) -> None:
        self._chat_repo = chat_repo
        self._session_store = session_store
        self._llm_client = llm_client

    async def process_turn_async(self, command: ProcessChatTurnCommand) -> ChatTurnDTO:
        """Process one conversation turn end to end (see IChatService)."""
        resolved_session_id: str = (
            str(command.session_id) if command.session_id is not None else str(uuid4())
        )
        loaded: ConversationStateDTO | None = await self._session_store.load_session_async(
            resolved_session_id
        )
        is_new_session: bool = loaded is None
        state: ConversationStateDTO = (
            loaded if loaded is not None else ConversationStateDTO(session_id=resolved_session_id)
        )

        log: structlog.BoundLogger = logger.bind(
            session_id=state.session_id,
            current_module=state.current_module,
        )
        log.info("chat_request_received", message_length=len(command.message))

        state.conversation_history.append({"role": "user", "content": command.message})

        # Snapshot completion before extraction to detect newly completed modules
        prev_completion: CompletionStatus = state.completion_status.model_copy()

        extraction_prompt: str = build_extraction_prompt(state)
        extracted: dict[str, object]
        try:
            extracted = await self._llm_client.chat_with_tools_async(
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
            state.borrowing_capacity = await estimate_borrowing_capacity_async(
                state.collected_data.m4
            )

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
        reply: str = await self._llm_client.complete_async(question_prompt, command.message)

        state.conversation_history.append({"role": "assistant", "content": reply})

        await self._session_store.save_session_async(state)

        user_needs: UserNeeds = build_user_needs(state.collected_data, state.session_id)
        routing = classify_intent(command.message, state, user_needs)
        log.info("chat_response_ready", has_routing=routing is not None)

        # Write initial_intent when M1 first completes this turn
        m1_just_completed: bool = state.completion_status.M1 and not prev_completion.M1
        if m1_just_completed and state.initial_intent is None:
            state.initial_intent = (
                routing.intent if routing is not None else EUserIntent.OPEN_ENDED_QUERY
            )

        # Persist to Postgres whenever a new session starts or any module newly completes
        newly_completed: bool = any(
            state.completion_status[m] and not prev_completion[m] for m in ESubmodel
        )
        should_persist: bool = is_new_session or newly_completed
        if should_persist:
            await self._chat_repo.upsert_chat_snapshot_async(state, command.anon_id)

        return ChatTurnDTO(
            reply=reply,
            extracted=extracted,
            state=state,
            routing=routing,
            should_persist=should_persist,
        )

    async def restore_session_async(
        self, command: RestoreChatSessionCommand
    ) -> ChatSessionRestoreDTO:
        """Resolve session state from Redis, falling back to Postgres (see IChatService)."""
        session_id_str: str = str(command.session_id)

        redis_state: ConversationStateDTO | None = await self._session_store.load_session_async(
            session_id_str
        )
        if redis_state is not None:
            return ChatSessionRestoreDTO(
                resume_message=None,
                state=redis_state,
                conversation_history=redis_state.conversation_history,
            )

        log: structlog.BoundLogger = logger.bind(session_id=session_id_str)

        db_state: ConversationStateDTO | None = await self._chat_repo.get_chat_snapshot_async(
            command.session_id
        )
        if db_state is None:
            raise SessionNotFoundError(session_id_str)

        log.info("session_restore_from_db")

        db_state.completion_status = recalculate_completion(db_state.collected_data)
        db_state.current_module = get_current_module(db_state.completion_status)

        restore_prompt: str = build_session_restore_prompt(db_state)
        resume_message: str = await self._llm_client.complete_async(
            restore_prompt, "Please write a welcome-back message."
        )
        log.info("session_restore_message_generated")

        db_state.conversation_history.append({"role": "assistant", "content": resume_message})

        try:
            await self._session_store.save_session_async(db_state)
        except Exception:
            log.warning("redis_reseed_failed")

        return ChatSessionRestoreDTO(
            resume_message=resume_message,
            state=db_state,
            conversation_history=[],
        )

    async def generate_summary_async(self, command: GenerateChatSummaryCommand) -> ChatSummaryDTO:
        """Generate a natural-language requirements summary (see IChatService)."""
        all_none: bool = all(
            value is None
            for submodel in ESubmodel
            for value in getattr(command.collected_data, submodel).model_dump().values()
        )
        if all_none:
            logger.warning("summary_rejected_all_none")
            raise SummaryValidationError("No data collected — cannot generate summary.")

        logger.info("summary_request_received")
        system_prompt: str = build_summary_prompt(command.collected_data)
        reply: str = await self._llm_client.complete_async(
            system_prompt, "Please generate the requirements summary."
        )
        logger.info("summary_generated", summary_length=len(reply))
        user_needs: UserNeeds = build_user_needs(
            command.collected_data, command.session_id, command.initial_intent
        )
        return ChatSummaryDTO(summary_text=reply, user_needs=user_needs)

    async def list_chats_async(self, command: ListChatSessionsCommand) -> list[ChatSessionDTO]:
        """Return all chat sessions for an anonymous user (see IChatService)."""
        return await self._chat_repo.list_chats_by_anon_async(command.anon_id)


def get_chat_service(
    chat_repo: Annotated[IChatRepository, Depends(get_chat_repository)],
) -> IChatService:
    """FastAPI dependency — returns a ChatService wired to its own chat repository."""
    return ChatService(chat_repo=chat_repo)
