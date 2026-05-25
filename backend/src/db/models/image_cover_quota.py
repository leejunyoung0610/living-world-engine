"""Replicate 등 월드 커버 이미지 생성 — 월별 쿼터."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class UserMonthlyCoverQuota(Base):
    """계정당 `YYYY-MM` 기준 커버 생성 횟수."""

    __tablename__ = "user_monthly_cover_quotas"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    year_month: Mapped[str] = mapped_column(String(7), primary_key=True)
    generation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class WorldMonthlyCoverQuota(Base):
    """월드당 `YYYY-MM` 기준 커버 생성 횟수 (재생성 상한용)."""

    __tablename__ = "world_monthly_cover_quotas"

    world_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("worlds.id", ondelete="CASCADE"),
        primary_key=True,
    )
    year_month: Mapped[str] = mapped_column(String(7), primary_key=True)
    generation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
