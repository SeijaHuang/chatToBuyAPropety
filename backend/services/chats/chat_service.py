"""Chat turn orchestration — the process-flow layer behind the chat endpoints.

Routers only resolve dependencies and shape HTTP responses; every multi-step
orchestration decision (session load/create, LLM rounds, field merging, financial
recompute, intent classification, session-restore strategy, summary generation)
lives here. This module sequences calls into conversation/ (state rules),
domain/ (pure business calculations, LLM gateway), and the repository/session-store
layer — it owns no business rule of its own.
"""

import json
from dataclasses import dataclass
from typing import Annotated, Protocol
from uuid import UUID, uuid4

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
from exceptions import BadRequestError, SessionNotFoundError, SummaryValidationError
from models.chat import RoutingPayload
from models.conversation_state import (
    CollectedData,
    CompletionStatus,
    ConversationStateDTO,
    ESubmodel,
    EUserIntent,
    M3SuburbPreference,
    M4Budget,
)
from models.user_needs import UserNeeds
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


@dataclass(frozen=True)
class ChatTurnResult:
    """Outcome of processing one POST /chat turn.

    Attributes:
        reply: Assistant reply text from the Round 2 question-generation call.
        extracted: Fields extracted by Round 1 (empty dict on tool-call parse failure).
        state: Fully updated conversation state after this turn (already persisted).
        routing: Populated when the turn completes requirements or matches a keyword.
        should_persist: True when a Postgres upsert was performed this turn — true
            for a brand-new session or when any module newly completed this turn.
    """

    reply: str
    extracted: dict[str, object]
    state: ConversationStateDTO
    routing: RoutingPayload | None
    should_persist: bool


@dataclass(frozen=True)
class SessionRestoreResult:
    """Outcome of resolving GET /chat/{session_id}.

    Attributes:
        resume_message: None on a Redis hit; the LLM-generated welcome-back string
            on a Postgres-fallback restore.
        state: Resolved conversation state — the live Redis copy, or the
            reconstructed Postgres snapshot with completion_status/current_module
            re-derived (neither is persisted, so both must be recomputed).
        conversation_history: Full history on a Redis hit; empty on a Postgres
            restore, since raw history is never persisted to Postgres.
    """

    resume_message: str | None
    state: ConversationStateDTO
    conversation_history: list[dict[str, object]]


@dataclass(frozen=True)
class SummaryResult:
    """Outcome of generating a natural-language requirements summary.

    Attributes:
        summary_text: LLM-generated summary covering all non-None collected fields.
        user_needs: Part 1 → Part 2 handoff snapshot built from the same data.
    """

    summary_text: str
    user_needs: UserNeeds


class IChatService(Protocol):
    """Process-orchestration contract behind the chat endpoints."""

    async def process_turn_async(
        self,
        session_id: str | None,
        message: str,
        anon_id: str,
    ) -> ChatTurnResult:
        """Process one conversation turn end to end.

        Args:
            session_id: Existing session UUID, or None to create a new session.
            message: The user's message text for this turn.
            anon_id: Anonymous user identity, used for the Postgres upsert.

        Returns:
            ChatTurnResult describing the reply, updated state, and whether a
            Postgres upsert was performed this turn.
        """
        ...

    async def restore_session_async(
        self,
        session_id: str,
    ) -> SessionRestoreResult:
        """Resolve session state from Redis, falling back to Postgres on a miss.

        Args:
            session_id: Session identifier, in principle a UUID v4 string.

        Returns:
            SessionRestoreResult on a Redis or Postgres hit.

        Raises:
            BadRequestError: When session_id is not a valid UUID string.
            SessionNotFoundError: When neither store has the session.
        """
        ...

    async def generate_summary_async(
        self,
        collected_data: CollectedData,
        session_id: str,
        initial_intent: EUserIntent,
    ) -> SummaryResult:
        """Generate a natural-language requirements summary.

        Args:
            collected_data: Accumulated field values from the conversation.
            session_id: Session identifier for the UserNeeds handoff snapshot.
            initial_intent: Intent classified at M1 completion.

        Returns:
            SummaryResult with the generated text and UserNeeds snapshot.

        Raises:
            SummaryValidationError: When every field across all sub-models is None.
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

    async def process_turn_async(
        self,
        session_id: str | None,
        message: str,
        anon_id: str,
    ) -> ChatTurnResult:
        """Process one conversation turn end to end (see IChatService)."""
        resolved_session_id: str = session_id if session_id else str(uuid4())
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
        log.info("chat_request_received", message_length=len(message))

        state.conversation_history.append({"role": "user", "content": message})

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
        reply: str = await self._llm_client.complete_async(question_prompt, message)

        state.conversation_history.append({"role": "assistant", "content": reply})

        await self._session_store.save_session_async(state)

        user_needs: UserNeeds = build_user_needs(state.collected_data, state.session_id)
        routing: RoutingPayload | None = classify_intent(message, state, user_needs)
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
            await self._chat_repo.upsert_chat_snapshot_async(state, anon_id)

        return ChatTurnResult(
            reply=reply,
            extracted=extracted,
            state=state,
            routing=routing,
            should_persist=should_persist,
        )

    async def restore_session_async(
        self,
        session_id: str,
    ) -> SessionRestoreResult:
        """Resolve session state from Redis, falling back to Postgres (see IChatService)."""
        try:
            UUID(session_id)
        except ValueError:
            raise BadRequestError(f"Invalid session_id: '{session_id}' is not a valid UUID.")

        redis_state: ConversationStateDTO | None = await self._session_store.load_session_async(
            session_id
        )
        if redis_state is not None:
            return SessionRestoreResult(
                resume_message=None,
                state=redis_state,
                conversation_history=redis_state.conversation_history,
            )

        log: structlog.BoundLogger = logger.bind(session_id=session_id)

        db_state: ConversationStateDTO | None = await self._chat_repo.get_chat_snapshot_async(
            session_id
        )
        if db_state is None:
            raise SessionNotFoundError(session_id)

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

        return SessionRestoreResult(
            resume_message=resume_message,
            state=db_state,
            conversation_history=[],
        )

    async def generate_summary_async(
        self,
        collected_data: CollectedData,
        session_id: str,
        initial_intent: EUserIntent,
    ) -> SummaryResult:
        """Generate a natural-language requirements summary (see IChatService)."""
        all_none: bool = all(
            value is None
            for submodel in ESubmodel
            for value in getattr(collected_data, submodel).model_dump().values()
        )
        if all_none:
            logger.warning("summary_rejected_all_none")
            raise SummaryValidationError("No data collected — cannot generate summary.")

        logger.info("summary_request_received")
        system_prompt: str = build_summary_prompt(collected_data)
        reply: str = await self._llm_client.complete_async(
            system_prompt, "Please generate the requirements summary."
        )
        logger.info("summary_generated", summary_length=len(reply))
        user_needs: UserNeeds = build_user_needs(collected_data, session_id, initial_intent)
        return SummaryResult(summary_text=reply, user_needs=user_needs)


def get_chat_service(
    chat_repo: Annotated[IChatRepository, Depends(get_chat_repository)],
) -> IChatService:
    """FastAPI dependency — returns a ChatService wired to its own chat repository."""
    return ChatService(chat_repo=chat_repo)
