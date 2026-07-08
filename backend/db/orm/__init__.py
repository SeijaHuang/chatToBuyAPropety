"""ORM model registry — import all Row classes here so Alembic can discover them."""

from db.orm.base import Base
from db.orm.chat import ChatRow
from db.orm.user import UserRow

__all__ = ["Base", "ChatRow", "UserRow"]
