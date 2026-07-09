"""Service-layer command for GET /chats."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ListChatSessionsCommand:
    """Parameters for IChatService.list_chats_async, built by the router.

    Attributes:
        anon_id: Anonymous user identity, parsed from the HttpOnly cookie.
    """

    anon_id: UUID
