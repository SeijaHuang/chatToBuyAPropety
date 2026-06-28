"""ORM model for the chats table."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.models.base import Base


class ChatRow(Base):
    """ORM mapping for the chats table.

    Stores one row per conversation session. Progressive upserts accumulate
    collected_data as each module (M1–M4) is completed.
    """

    __tablename__ = "chats"

    __table_args__ = (
        CheckConstraint(
            "NOT (user_id IS NOT NULL AND anon_id IS NOT NULL)",
            name="chk_chats_single_owner",
        ),
        Index("idx_chats_status", "status"),
        Index("idx_chats_updated_at", "updated_at"),
        Index("idx_chats_user_id", "user_id", postgresql_where="user_id IS NOT NULL"),
        Index("idx_chats_anon_id", "anon_id", postgresql_where="anon_id IS NOT NULL"),
    )

    # Identity — column name matches session_id used everywhere else
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)

    # Owner — FK constraints added in P1-B
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    anon_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Conversation state
    status: Mapped[str] = mapped_column(Text, nullable=False, default="IN_PROGRESS")
    schema_version: Mapped[str] = mapped_column(Text, nullable=False, default="1.1")
    initial_intent: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Structured business data
    collected_data: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    final_needs: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    borrowing_capacity: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
