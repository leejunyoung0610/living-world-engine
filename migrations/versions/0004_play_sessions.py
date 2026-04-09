"""play_sessions table for persistent browser play

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-09

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "play_sessions",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("world_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("turn", sa.Integer(), server_default="0", nullable=False),
        sa.Column("day", sa.Integer(), server_default="1", nullable=False),
        sa.Column("last_preview", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["world_id"], ["worlds.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "world_id", name="uq_play_sessions_user_world"),
    )
    op.create_index(op.f("ix_play_sessions_user_id"), "play_sessions", ["user_id"], unique=False)
    op.create_index(op.f("ix_play_sessions_world_id"), "play_sessions", ["world_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_play_sessions_world_id"), table_name="play_sessions")
    op.drop_index(op.f("ix_play_sessions_user_id"), table_name="play_sessions")
    op.drop_table("play_sessions")
