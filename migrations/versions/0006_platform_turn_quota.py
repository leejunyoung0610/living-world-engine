"""platform daily turn quota (user_daily_turn_usage, users.uses_platform_llm)

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-17

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "uses_platform_llm",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.create_table(
        "user_daily_turn_usage",
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("turn_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "usage_date"),
    )


def downgrade() -> None:
    op.drop_table("user_daily_turn_usage")
    op.drop_column("users", "uses_platform_llm")
