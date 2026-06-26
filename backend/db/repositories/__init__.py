"""Repository registry — re-export all repository classes and dependency providers."""

from db.repositories.chat import IChatRepository, SqlAlchemyChatRepository, get_chat_repository

__all__ = ["IChatRepository", "SqlAlchemyChatRepository", "get_chat_repository"]
