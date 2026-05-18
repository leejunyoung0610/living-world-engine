"""world_user_likes + worlds.like_count

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-12

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "worlds",
        sa.Column(
            "like_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_table(
        "world_user_likes",
        sa.Column("world_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["world_id"], ["worlds.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("world_id", "user_id"),
    )
    op.create_index(
        "ix_world_user_likes_user_id",
        "world_user_likes",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_world_user_likes_user_id", table_name="world_user_likes")
    op.drop_table("world_user_likes")
    op.drop_column("worlds", "like_count")
