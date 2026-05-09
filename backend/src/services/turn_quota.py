"""플랫폼 키 일일 턴 쿼터 (Epic D) — UTC 달력일 기준."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Protocol

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import UserDailyTurnUsage
from ..utils.config import Settings


class _QuotaUser(Protocol):
    id: object


def utc_usage_date() -> date:
    """일일 리셋 기준: UTC 자정 (`UGC_MVP_PLAN` §8)."""
    return datetime.now(timezone.utc).date()


def platform_quota_enforced(settings: Settings) -> bool:
    """플랫폼 키 단일 경로 — 일일 턴 한도 적용 여부."""
    if not settings.enforce_platform_turn_quota:
        return False
    lim = settings.platform_daily_turn_limit
    if lim is None or lim < 1:
        return False
    return True


def check_platform_turn_quota_or_raise(db: Session, user: _QuotaUser, settings: Settings) -> None:
    """`POST .../turn` 호출 전 — 한도에 이미 도달했으면 429."""
    if not platform_quota_enforced(settings):
        return
    limit = settings.platform_daily_turn_limit
    assert limit is not None
    today = utc_usage_date()
    row = db.scalars(
        select(UserDailyTurnUsage).where(
            UserDailyTurnUsage.user_id == user.id,
            UserDailyTurnUsage.usage_date == today,
        )
    ).first()
    used = int(row.turn_count) if row is not None else 0
    if used >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"오늘 플랫폼 턴 한도({limit}턴)에 도달했습니다. "
                "내일 UTC 기준으로 다시 시도하세요."
            ),
        )


def record_platform_turn(db: Session, user: _QuotaUser, settings: Settings) -> None:
    """턴이 성공한 뒤 집계. `_persist_session` 의 `commit` 과 같은 트랜잭션에 포함되도록 flush 만 사용."""
    if not platform_quota_enforced(settings):
        return
    today = utc_usage_date()
    row = db.scalars(
        select(UserDailyTurnUsage).where(
            UserDailyTurnUsage.user_id == user.id,
            UserDailyTurnUsage.usage_date == today,
        )
    ).first()
    if row is None:
        row = UserDailyTurnUsage(user_id=user.id, usage_date=today, turn_count=0)
        db.add(row)
    row.turn_count = int(row.turn_count) + 1
    db.flush()
