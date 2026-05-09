"""kakao oauth — kakao_sub, auth_provider, password_hash nullable

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-10

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "auth_provider",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'local'"),
        ),
    )
    op.add_column(
        "users",
        sa.Column("kakao_sub", sa.String(length=64), nullable=True),
    )
    op.create_index(
        op.f("ix_users_kakao_sub"),
        "users",
        ["kakao_sub"],
        unique=True,
    )
    # 소셜 가입 사용자는 비밀번호가 없을 수 있음
    op.alter_column("users", "password_hash", existing_type=sa.LargeBinary(), nullable=True)


def downgrade() -> None:
    op.alter_column("users", "password_hash", existing_type=sa.LargeBinary(), nullable=False)
    op.drop_index(op.f("ix_users_kakao_sub"), table_name="users")
    op.drop_column("users", "kakao_sub")
    op.drop_column("users", "auth_provider")
