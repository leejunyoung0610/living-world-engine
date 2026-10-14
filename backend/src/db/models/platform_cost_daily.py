"""UTC 일자별 플랫폼(과금) 턴 추정 비용 누적 (Epic E)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from ..types import MONEY


class PlatformCostDaily(Base):
    __tablename__ = "platform_cost_daily"

    usage_date: Mapped[date] = mapped_column(Date, primary_key=True)
    cost_usd: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, server_default="0", default=Decimal("0")
    )
    alert_sent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )
