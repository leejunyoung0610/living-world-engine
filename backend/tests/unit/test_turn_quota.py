"""플랫폼 턴 쿼터 정책 단위 테스트."""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.src.db.base import Base
from backend.src.db.models import User, UserDailyTurnUsage
from backend.src.services.turn_quota import (
    platform_quota_enforced,
    release_platform_turn,
    reserve_platform_turn,
    utc_usage_date,
)
from backend.src.utils.config import Settings


def test_utc_usage_date_is_today_utc() -> None:
    from datetime import datetime, timezone

    assert utc_usage_date() == datetime.now(timezone.utc).date()


@pytest.fixture
def settings_on(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("ENFORCE_PLATFORM_TURN_QUOTA", "true")
    monkeypatch.setenv("PLATFORM_DAILY_TURN_LIMIT", "20")
    return Settings()


def test_platform_quota_enforced_when_config_on(settings_on: Settings) -> None:
    assert platform_quota_enforced(settings_on) is True


def test_platform_quota_off_when_limit_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENFORCE_PLATFORM_TURN_QUOTA", "true")
    monkeypatch.setenv("PLATFORM_DAILY_TURN_LIMIT", "0")
    s = Settings()
    assert platform_quota_enforced(s) is False


# --- 원자적 예약·되돌리기 (SQLite) ---


@pytest.fixture
def quota_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False)
    s = SessionLocal()
    user = User(email=f"{uuid.uuid4().hex[:8]}@example.com", username="q")
    s.add(user)
    s.commit()
    try:
        yield s, user, SessionLocal
    finally:
        s.close()


def _count(s, user) -> int | None:
    return s.scalar(
        select(UserDailyTurnUsage.turn_count).where(UserDailyTurnUsage.user_id == user.id)
    )


def test_reserve_counts_up_to_limit_then_429(quota_db, monkeypatch: pytest.MonkeyPatch) -> None:
    s, user, _ = quota_db
    monkeypatch.setenv("ENFORCE_PLATFORM_TURN_QUOTA", "true")
    monkeypatch.setenv("PLATFORM_DAILY_TURN_LIMIT", "2")
    settings = Settings()

    assert reserve_platform_turn(s, user.id, settings) == utc_usage_date()
    assert reserve_platform_turn(s, user.id, settings) == utc_usage_date()
    with pytest.raises(HTTPException) as ei:
        reserve_platform_turn(s, user.id, settings)
    assert ei.value.status_code == 429
    assert "한도(2턴)" in ei.value.detail
    assert _count(s, user) == 2  # 거부된 요청은 아무것도 바꾸지 않음


def test_reserve_is_committed_immediately(quota_db, monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM 호출 중 잠금을 잡지 않도록 예약은 바로 commit — 다른 세션에서 보인다."""
    s, user, SessionLocal = quota_db
    monkeypatch.setenv("ENFORCE_PLATFORM_TURN_QUOTA", "true")
    monkeypatch.setenv("PLATFORM_DAILY_TURN_LIMIT", "3")
    reserve_platform_turn(s, user.id, Settings())
    with SessionLocal() as other:
        assert _count(other, user) == 1


def test_release_undoes_reservation_and_never_goes_negative(
    quota_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    s, user, _ = quota_db
    monkeypatch.setenv("ENFORCE_PLATFORM_TURN_QUOTA", "true")
    monkeypatch.setenv("PLATFORM_DAILY_TURN_LIMIT", "1")
    settings = Settings()

    reserved = reserve_platform_turn(s, user.id, settings)
    release_platform_turn(s, user.id, reserved)
    assert _count(s, user) == 0
    release_platform_turn(s, user.id, reserved)  # 중복 호출에도 0 미만 금지
    assert _count(s, user) == 0
    # 되돌린 1턴은 다시 쓸 수 있다
    assert reserve_platform_turn(s, user.id, settings) is not None


def test_reserve_noop_when_quota_not_enforced(quota_db, monkeypatch: pytest.MonkeyPatch) -> None:
    s, user, _ = quota_db
    monkeypatch.setenv("ENFORCE_PLATFORM_TURN_QUOTA", "false")
    assert reserve_platform_turn(s, user.id, Settings()) is None
    assert _count(s, user) is None  # 행도 만들지 않음
    release_platform_turn(s, user.id, None)  # 예약 없음 → 아무 일도 없음
