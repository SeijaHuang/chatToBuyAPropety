"""FastAPI dependencies for resolving anonymous user identity from HttpOnly cookie."""

import uuid
from typing import Annotated

import structlog
from fastapi import Cookie, Depends

from db.repositories.user import IUserRepository, get_user_repository
from exceptions import BadRequestError

logger = structlog.get_logger()


async def resolve_anon_id_async(
    anon_repo: Annotated[IUserRepository, Depends(get_user_repository)],
    propertyai_anon_id: Annotated[str | None, Cookie()] = None,
) -> str:
    """Read anon_id from HttpOnly cookie and resolve to a DB-backed identity.

    On first request (no cookie): creates a new user row and returns the new anon_id.
    On subsequent requests: refreshes updated_at and returns the existing anon_id.
    On malformed cookie value: treats as absent, creates fresh identity.

    Args:
        anon_repo: User repository for DB access.
        propertyai_anon_id: Raw cookie value injected by FastAPI; None if absent.

    Returns:
        A non-None str guaranteed to correspond to an existing users row.
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
) -> str:
    """Require a valid anon_id cookie; raise 400 if absent or not a valid UUID.

    Used by read-only endpoints (GET /chats) that should not auto-create users.

    Args:
        propertyai_anon_id: Raw cookie value injected by FastAPI; None if absent.

    Returns:
        The validated anon_id string.

    Raises:
        BadRequestError: When the cookie is absent or its value is not a valid UUID.
    """
    if propertyai_anon_id is None:
        raise BadRequestError("propertyai_anon_id cookie is required.")
    try:
        uuid.UUID(propertyai_anon_id)
    except ValueError:
        raise BadRequestError(f"Invalid anon_id cookie value: '{propertyai_anon_id}'.")
    return propertyai_anon_id
