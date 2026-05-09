"""사용자 — 인증 (로컬 + 카카오 OAuth)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, LargeBinary, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    #: 비번 가입 사용자만 채워짐. 소셜 전용은 ``None``.
    password_hash: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    #: ``"local"`` | ``"kakao"`` — 첫 로그인 경로.
    auth_provider: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="local", default="local"
    )
    #: 카카오 사용자 unique id (`id` 또는 OIDC `sub`). 다른 공급자가 늘면 컬럼 추가.
    kakao_sub: Mapped[str | None] = mapped_column(String(64), unique=True, index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
