"""NPC 초상 생성 — 계정당·월드당 월별 쿼터."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class UserMonthlyAvatarQuota(Base):
    __tablename__ = "user_monthly_avatar_quotas"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    year_month: Mapped[str] = mapped_column(String(7), primary_key=True)
    generation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class WorldMonthlyAvatarQuota(Base):
    __tablename__ = "world_monthly_avatar_quotas"

    world_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("worlds.id", ondelete="CASCADE"),
        primary_key=True,
    )
    year_month: Mapped[str] = mapped_column(String(7), primary_key=True)
    generation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
