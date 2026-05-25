"""월드 커버 AI(Replicate) — 계정당·월드당 월별 생성 횟수

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-26

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_monthly_cover_quotas",
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("year_month", sa.String(length=7), nullable=False),
        sa.Column(
            "generation_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "year_month"),
    )
    op.create_table(
        "world_monthly_cover_quotas",
        sa.Column("world_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("year_month", sa.String(length=7), nullable=False),
        sa.Column(
            "generation_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.ForeignKeyConstraint(["world_id"], ["worlds.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("world_id", "year_month"),
    )


def downgrade() -> None:
    op.drop_table("world_monthly_cover_quotas")
    op.drop_table("user_monthly_cover_quotas")
