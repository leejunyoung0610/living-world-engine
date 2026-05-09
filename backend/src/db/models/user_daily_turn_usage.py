"""유저별 UTC 일자 단위 플랫폼 턴 사용량 (Epic D)."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class UserDailyTurnUsage(Base):
    """`(user_id, usage_date)` 복합 PK — 멀티 워커에서도 동일 행만 갱신."""

    __tablename__ = "user_daily_turn_usage"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    usage_date: Mapped[date] = mapped_column(Date, primary_key=True)
    turn_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
