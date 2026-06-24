"""ORM model registry — import all Row classes here so Alembic can discover them."""

from db.models.base import Base
from db.models.chat import ChatRow

__all__ = ["Base", "ChatRow"]
