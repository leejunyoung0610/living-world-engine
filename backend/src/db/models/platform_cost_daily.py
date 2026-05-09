"""UTC 일자별 플랫폼(과금) 턴 추정 비용 누적 (Epic E)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, Float
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class PlatformCostDaily(Base):
    __tablename__ = "platform_cost_daily"

    usage_date: Mapped[date] = mapped_column(Date, primary_key=True)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, server_default="0", default=0.0)
    alert_sent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )
