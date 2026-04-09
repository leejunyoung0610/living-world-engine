"""유저·월드별 브라우저 플레이 진행 — 엔진 스냅샷 JSON."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Text, Uuid, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class PlaySession(Base):
    __tablename__ = "play_sessions"
    __table_args__ = (
        UniqueConstraint("user_id", "world_id", name="uq_play_sessions_user_world"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    world_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("worlds.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    turn: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    day: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1", default=1)
    last_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
