"""worlds: genres JSON + play_start_count

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-18

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "worlds",
        sa.Column(
            "genres",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.add_column(
        "worlds",
        sa.Column(
            "play_start_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("worlds", "play_start_count")
    op.drop_column("worlds", "genres")
