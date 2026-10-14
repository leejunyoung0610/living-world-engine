"""금액 컬럼 Float → Numeric(12, 6)

`platform_cost_daily.cost_usd`(0008)·`image_gen_cost_daily.cost_usd`(0014)는
double precision 이라 턴마다 소액을 누적할 때 이진 부동소수 오차가 쌓인다.
고정 소수 NUMERIC(12, 6) — 최대 999,999.999999 USD, 1e-6 USD 단위 — 로 바꾼다.

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-14

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

MONEY_TABLES = ("platform_cost_daily", "image_gen_cost_daily")


def upgrade() -> None:
    for table in MONEY_TABLES:
        op.alter_column(
            table,
            "cost_usd",
            existing_type=sa.Float(),
            type_=sa.Numeric(precision=12, scale=6),
            existing_nullable=False,
            server_default=sa.text("0"),
            existing_server_default=sa.text("0"),
            postgresql_using="round(cost_usd::numeric, 6)",
        )


def downgrade() -> None:
    for table in MONEY_TABLES:
        op.alter_column(
            table,
            "cost_usd",
            existing_type=sa.Numeric(precision=12, scale=6),
            type_=sa.Float(),
            existing_nullable=False,
            server_default=sa.text("0"),
            existing_server_default=sa.text("0"),
            postgresql_using="cost_usd::double precision",
        )
