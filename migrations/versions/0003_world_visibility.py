"""world visibility public/private

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-29

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "worlds",
        sa.Column(
            "visibility",
            sa.String(length=20),
            server_default="private",
            nullable=False,
        ),
    )
    op.create_index(op.f("ix_worlds_visibility"), "worlds", ["visibility"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_worlds_visibility"), table_name="worlds")
    op.drop_column("worlds", "visibility")
