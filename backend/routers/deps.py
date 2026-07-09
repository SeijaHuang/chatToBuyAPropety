"""FastAPI dependencies for resolving anonymous user identity from HttpOnly cookie."""

import uuid
from typing import Annotated

import structlog
from fastapi import Cookie, Depends

from db.repositories.user import IUserRepository, get_user_repository
from exceptions import BadRequestError
from models.requests.post_chat import ChatRequest

logger = structlog.get_logger()


async def resolve_anon_id_async(
    anon_repo: Annotated[IUserRepository, Depends(get_user_repository)],
    propertyai_anon_id: Annotated[str | None, Cookie()] = None,
) -> uuid.UUID:
    """Read anon_id from HttpOnly cookie and resolve to a DB-backed identity.

    On first request (no cookie): creates a new user row and returns the new anon_id.
    On subsequent requests: refreshes updated_at and returns the existing anon_id.
    On malformed cookie value: treats as absent, creates fresh identity.

    Args:
        anon_repo: User repository for DB access.
        propertyai_anon_id: Raw cookie value injected by FastAPI; None if absent.

    Returns:
        The anon_id UUID guaranteed to correspond to an existing users row.
    """
    parsed_anon_id: uuid.UUID | None = None
    if propertyai_anon_id is not None:
        try:
            parsed_anon_id = uuid.UUID(propertyai_anon_id)
        except ValueError:
            logger.warning("anon_id_parse_failed", raw_anon_id=propertyai_anon_id)
    return await anon_repo.get_or_create_async(parsed_anon_id)


async def require_anon_id_cookie_async(
    propertyai_anon_id: Annotated[str | None, Cookie()] = None,
) -> uuid.UUID:
    """Require a valid anon_id cookie; raise 400 if absent or not a valid UUID.

    Used by read-only endpoints (GET /chats) that should not auto-create users.

    Args:
        propertyai_anon_id: Raw cookie value injected by FastAPI; None if absent.

    Returns:
        The parsed anon_id UUID.

    Raises:
        BadRequestError: When the cookie is absent or its value is not a valid UUID.
    """
    if propertyai_anon_id is None:
        raise BadRequestError("propertyai_anon_id cookie is required.")
    try:
        return uuid.UUID(propertyai_anon_id)
    except ValueError:
        raise BadRequestError(f"Invalid anon_id cookie value: '{propertyai_anon_id}'.")


async def require_valid_session_id_async(session_id: str) -> uuid.UUID:
    """Validate the session_id path parameter for GET /chat/{session_id}.

    Args:
        session_id: Raw path segment injected by FastAPI.

    Returns:
        The parsed session_id UUID.

    Raises:
        BadRequestError: When session_id is not a valid UUID string.
    """
    try:
        return uuid.UUID(session_id)
    except ValueError:
        raise BadRequestError(f"Invalid session_id: '{session_id}' is not a valid UUID.")


async def validate_optional_session_id_async(request: ChatRequest) -> uuid.UUID | None:
    """Validate the optional session_id field on the POST /chat body.

    Args:
        request: Parsed ChatRequest body.

    Returns:
        The parsed session_id UUID, or None when the request omits it (new session).

    Raises:
        BadRequestError: When session_id is present but not a valid UUID string.
    """
    if request.session_id is None:
        return None
    try:
        return uuid.UUID(request.session_id)
    except ValueError:
        raise BadRequestError(f"Invalid session_id: '{request.session_id}' is not a valid UUID.")
