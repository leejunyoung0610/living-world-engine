"""플랫폼 키 일일 턴 쿼터 (Epic D) — UTC 달력일 기준.

한도 검사와 차감은 조건부 UPDATE 한 문장으로 원자적으로 처리한다::

    UPDATE user_daily_turn_usage SET turn_count = turn_count + 1
    WHERE user_id = :u AND usage_date = :d AND turn_count < :limit

영향 행이 0이면 이미 한도다. (예전처럼 SELECT 로 검사하고 LLM 호출 뒤 따로 +1 하면,
동시에 들어온 요청들이 같은 잔여분을 보고 모두 통과해 한도를 넘길 수 있었다.)
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..db.atomic import NO_SYNC, insert_ignore
from ..db.models import UserDailyTurnUsage
from ..utils.config import Settings

logger = logging.getLogger(__name__)


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


def reserve_platform_turn(db: Session, user_id: uuid.UUID, settings: Settings) -> date | None:
    """LLM 호출 **전** — 한도 안이면 오늘 사용량을 원자적으로 +1 하고 그 UTC 날짜를 반환.

    - 이미 한도면 429 (아무것도 바꾸지 않음).
    - 쿼터 미적용이면 ``None`` (예약 없음).
    - 예약은 즉시 commit 한다: LLM 호출(수 초) 동안 행 잠금·트랜잭션을 잡지 않기 위해서.
      턴이 실패하면 반환값을 ``release_platform_turn`` 에 넘겨 되돌린다.
      스트리밍 중 클라이언트가 끊긴 경우는 LLM 비용이 이미 발생했으므로 사용으로 남긴다.
    - ORM ``User`` 대신 id 를 받는다: commit 이 세션 객체를 만료시키므로, 세션이 닫힌 뒤
      실행되는 스트리밍 제너레이터에서 ``user.id`` 를 다시 읽으면 DetachedInstanceError.
    """
    if not platform_quota_enforced(settings):
        return None
    limit = settings.platform_daily_turn_limit
    assert limit is not None
    today = utc_usage_date()

    insert_ignore(
        db,
        UserDailyTurnUsage,
        {"user_id": user_id, "usage_date": today, "turn_count": 0},
    )
    result = db.execute(
        update(UserDailyTurnUsage)
        .where(
            UserDailyTurnUsage.user_id == user_id,
            UserDailyTurnUsage.usage_date == today,
            UserDailyTurnUsage.turn_count < limit,
        )
        .values(turn_count=UserDailyTurnUsage.turn_count + 1)
        .execution_options(**NO_SYNC)
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"오늘 플랫폼 턴 한도({limit}턴)에 도달했습니다. "
                "내일 UTC 기준으로 다시 시도하세요."
            ),
        )
    db.commit()
    return today


def release_platform_turn(db: Session, user_id: uuid.UUID, reserved_date: date | None) -> None:
    """실패한 턴의 예약을 되돌린다 (원자적 -1, 0 미만 방지). 실패 경로 전용.

    세션의 미커밋 변경(실패한 턴의 부분 기록)은 버리고, 차감 취소만 commit 한다.
    ``reserved_date`` 는 예약 시점 날짜 — 자정을 넘겨 실패해도 그날 행을 되돌린다.
    """
    if reserved_date is None:
        return
    try:
        db.rollback()
        db.execute(
            update(UserDailyTurnUsage)
            .where(
                UserDailyTurnUsage.user_id == user_id,
                UserDailyTurnUsage.usage_date == reserved_date,
                UserDailyTurnUsage.turn_count > 0,
            )
            .values(turn_count=UserDailyTurnUsage.turn_count - 1)
            .execution_options(**NO_SYNC)
        )
        db.commit()
    except SQLAlchemyError:
        # 되돌리기 실패가 원래 오류(LLM 실패 등) 응답을 가리지 않도록 기록만 한다.
        logger.exception("platform turn quota release failed")
        db.rollback()
