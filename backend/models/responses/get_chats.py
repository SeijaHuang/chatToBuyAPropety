"""Response type for GET /chats."""

from models.dto.get_chats import ChatSessionDTO

ChatSessionsResponse = list[ChatSessionDTO]
