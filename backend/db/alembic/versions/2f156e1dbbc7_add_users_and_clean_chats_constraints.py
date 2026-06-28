"""add_users_and_clean_chats_constraints

Revision ID: 2f156e1dbbc7
Revises: 993128e7e195
Create Date: 2026-06-28 20:26:31.002183

Two changes in one migration:

1. Create the unified `users` table.
   Replaces the previously planned two-table design (anonymous_users + users).
   Both anonymous and registered users share this table:
     - Anonymous: anon_id set, email = NULL
     - Registered: anon_id set, email filled in on registration (P1-B)
   user_id is the internal PK generated on first visit and never changes.

2. Drop CHECK CONSTRAINT chk_chats_single_owner from chats.
   The original constraint prevented user_id and anon_id from being simultaneously
   non-NULL, based on the old two-table assumption. With the single-table design,
   registered users also retain their anon_id. After P1-B auth lands, new chat rows
   may carry both identifiers simultaneously (anon_id = device identity,
   user_id = registered identity), so the mutual-exclusion constraint is dropped.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "2f156e1dbbc7"
down_revision: str | Sequence[str] | None = "993128e7e195"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create users table and drop single-owner constraint from chats."""
    op.create_table(
        "users",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("anon_id", sa.UUID(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("anon_id", name="uq_users_anon_id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("idx_users_anon_id", "users", ["anon_id"])

    op.drop_constraint("chk_chats_single_owner", "chats", type_="check")


def downgrade() -> None:
    """Drop users table and restore single-owner constraint on chats."""
    op.drop_index("idx_users_anon_id", table_name="users")
    op.drop_table("users")

    op.create_check_constraint(
        "chk_chats_single_owner",
        "chats",
        "NOT (user_id IS NOT NULL AND anon_id IS NOT NULL)",
    )
