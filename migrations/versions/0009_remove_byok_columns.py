"""remove per-user BYOK columns (platform ANTHROPIC_API_KEY only)

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-29

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("users", "anthropic_api_key_encrypted")
    op.drop_column("users", "uses_platform_llm")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "uses_platform_llm",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "users",
        sa.Column("anthropic_api_key_encrypted", sa.LargeBinary(), nullable=True),
    )
