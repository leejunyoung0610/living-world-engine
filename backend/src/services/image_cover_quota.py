"""월드 커버 AI 생성 월별 쿼터."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models.image_cover_quota import UserMonthlyCoverQuota, WorldMonthlyCoverQuota
from ..db.models.world import World
from ..utils.config import Settings


def _utc_year_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def assert_cover_quota_allows(
    db: Session,
    *,
    user_id: uuid.UUID,
    world_id: uuid.UUID,
    settings: Settings,
) -> None:
    """다음 1회 생성이 가능한지 검사. 초과 시 HTTP 429."""
    ym = _utc_year_month()
    user_limit = max(0, int(settings.image_gen_per_user_monthly))
    world_limit = max(0, int(settings.image_gen_per_world_monthly))

    urow = db.scalars(
        select(UserMonthlyCoverQuota).where(
            UserMonthlyCoverQuota.user_id == user_id,
            UserMonthlyCoverQuota.year_month == ym,
        )
    ).first()
    ucount = int(urow.generation_count) if urow is not None else 0
    if user_limit > 0 and ucount >= user_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"이번 달 커버 생성 한도({user_limit}회)에 도달했습니다.",
        )

    wrow = db.scalars(
        select(WorldMonthlyCoverQuota).where(
            WorldMonthlyCoverQuota.world_id == world_id,
            WorldMonthlyCoverQuota.year_month == ym,
        )
    ).first()
    wcount = int(wrow.generation_count) if wrow is not None else 0
    if world_limit > 0 and wcount >= world_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"이 월드의 이번 달 커버 생성·재생성 한도({world_limit}회)에 도달했습니다.",
        )


def persist_cover_generation(
    db: Session,
    *,
    user_id: uuid.UUID,
    world_id: uuid.UUID,
    image_url: str,
    world_row: World,
    settings: Settings,
) -> None:
    """Replicate 성공 후 쿼터 증가 + world_data.cover_image_url 저장."""
    _ = settings
    ym = _utc_year_month()
    urow = db.scalars(
        select(UserMonthlyCoverQuota).where(
            UserMonthlyCoverQuota.user_id == user_id,
            UserMonthlyCoverQuota.year_month == ym,
        )
    ).first()
    if urow is None:
        urow = UserMonthlyCoverQuota(user_id=user_id, year_month=ym, generation_count=0)
        db.add(urow)
        db.flush()

    wrow = db.scalars(
        select(WorldMonthlyCoverQuota).where(
            WorldMonthlyCoverQuota.world_id == world_id,
            WorldMonthlyCoverQuota.year_month == ym,
        )
    ).first()
    if wrow is None:
        wrow = WorldMonthlyCoverQuota(world_id=world_id, year_month=ym, generation_count=0)
        db.add(wrow)
        db.flush()

    urow.generation_count = int(urow.generation_count) + 1
    wrow.generation_count = int(wrow.generation_count) + 1

    wd = world_row.world_data if isinstance(world_row.world_data, dict) else {}
    new_wd = dict(wd)
    new_wd["cover_image_url"] = image_url
    world_row.world_data = new_wd
    db.add(world_row)
    db.flush()


def remaining_cover_quota(
    db: Session,
    *,
    user_id: uuid.UUID,
    world_id: uuid.UUID,
    settings: Settings,
) -> tuple[int | None, int | None]:
    """(계정 월 남은 횟수, 월드 월 남은 횟수) — limit 0이면 해당 축은 None(무제한 표시용)."""
    ym = _utc_year_month()
    user_limit = max(0, int(settings.image_gen_per_user_monthly))
    world_limit = max(0, int(settings.image_gen_per_world_monthly))

    urow = db.scalars(
        select(UserMonthlyCoverQuota).where(
            UserMonthlyCoverQuota.user_id == user_id,
            UserMonthlyCoverQuota.year_month == ym,
        )
    ).first()
    ucount = int(urow.generation_count) if urow is not None else 0
    wrow = db.scalars(
        select(WorldMonthlyCoverQuota).where(
            WorldMonthlyCoverQuota.world_id == world_id,
            WorldMonthlyCoverQuota.year_month == ym,
        )
    ).first()
    wcount = int(wrow.generation_count) if wrow is not None else 0

    user_rem: int | None = None if user_limit <= 0 else max(0, user_limit - ucount)
    world_rem: int | None = None if world_limit <= 0 else max(0, world_limit - wcount)
    return user_rem, world_rem
