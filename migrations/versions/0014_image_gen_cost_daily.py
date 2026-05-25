"""커버 이미지 생성 — UTC 일자별 추정 비용·건수 집계 (일 예산 알림용)

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-26

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "image_gen_cost_daily",
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("cost_usd", sa.Float(), server_default="0", nullable=False),
        sa.Column(
            "cover_generation_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "alert_sent",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("usage_date"),
    )


def downgrade() -> None:
    op.drop_table("image_gen_cost_daily")
