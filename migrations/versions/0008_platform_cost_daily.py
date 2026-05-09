"""platform daily estimated cost (Epic E)

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-17

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_cost_daily",
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("cost_usd", sa.Float(), server_default="0", nullable=False),
        sa.Column("alert_sent", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.PrimaryKeyConstraint("usage_date"),
    )


def downgrade() -> None:
    op.drop_table("platform_cost_daily")
