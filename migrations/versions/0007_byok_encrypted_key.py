"""user BYOK encrypted anthropic key

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-17

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("anthropic_api_key_encrypted", sa.LargeBinary(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "anthropic_api_key_encrypted")
