"""ORM model for the users table."""

import uuid
from datetime import datetime

from sqlalchemy import Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.orm.base import Base


class UserRow(Base):
    """ORM mapping for the users table.

    Covers both anonymous and registered users in a single table.
    Anonymous users have anon_id set (stored in frontend localStorage) and
    email = NULL. Registered users add email (and later password/OAuth) to
    the same row — no migration of chat rows required.
    """

    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # The UUID sent to/from frontend localStorage; always populated
    anon_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False)
    # NULL for anonymous users; populated when the user registers
    email: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
