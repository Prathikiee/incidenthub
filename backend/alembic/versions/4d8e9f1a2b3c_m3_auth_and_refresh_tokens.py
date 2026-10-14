"""Milestone 3: Add password hash to users and create refresh_tokens table.

Revision ID: 4d8e9f1a2b3c
Revises: 39ae0ff14533
Create Date: 2026-10-14 18:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4d8e9f1a2b3c"
down_revision: str | None = "39ae0ff14533"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add hashed_password column to users table
    op.add_column(
        "users",
        sa.Column("hashed_password", sa.String(length=255), nullable=True),
    )

    # 2. Create refresh_tokens persistence table
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_refresh_tokens_token_hash"),
        "refresh_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_refresh_tokens_user_id"),
        "refresh_tokens",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_refresh_tokens_user_id_token_hash",
        "refresh_tokens",
        ["user_id", "token_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_user_id_token_hash", table_name="refresh_tokens")
    op.drop_index(op.f("ix_refresh_tokens_user_id"), table_name="refresh_tokens")
    op.drop_index(op.f("ix_refresh_tokens_token_hash"), table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_column("users", "hashed_password")
