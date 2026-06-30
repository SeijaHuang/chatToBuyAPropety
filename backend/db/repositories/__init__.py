"""Repository registry — re-export all repository classes and dependency providers."""

from db.repositories.chat import IChatRepository, get_chat_repository
from db.repositories.user import IUserRepository, get_user_repository

__all__ = [
    "IChatRepository",
    "get_chat_repository",
    "IUserRepository",
    "get_user_repository",
]
