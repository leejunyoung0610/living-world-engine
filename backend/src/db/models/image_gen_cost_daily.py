"""UTC 일자별 이미지(커버) 생성 건수·추정 USD — 일 예산·알림."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, Integer
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from ..types import MONEY


class ImageGenCostDaily(Base):
    __tablename__ = "image_gen_cost_daily"

    usage_date: Mapped[date] = mapped_column(Date, primary_key=True)
    cost_usd: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, server_default="0", default=Decimal("0")
    )
    cover_generation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        default=0,
    )
    npc_avatar_generation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        default=0,
    )
    alert_sent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )
