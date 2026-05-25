"""NPC 초상(Replicate 등) 월별 쿼터 + 일 집계에 npc 카운터

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-26

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_monthly_avatar_quotas",
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("year_month", sa.String(length=7), nullable=False),
        sa.Column(
            "generation_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "year_month"),
    )
    op.create_table(
        "world_monthly_avatar_quotas",
        sa.Column("world_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("year_month", sa.String(length=7), nullable=False),
        sa.Column(
            "generation_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.ForeignKeyConstraint(["world_id"], ["worlds.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("world_id", "year_month"),
    )
    op.add_column(
        "image_gen_cost_daily",
        sa.Column(
            "npc_avatar_generation_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("image_gen_cost_daily", "npc_avatar_generation_count")
    op.drop_table("world_monthly_avatar_quotas")
    op.drop_table("user_monthly_avatar_quotas")
