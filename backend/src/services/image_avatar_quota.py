"""NPC 초상(Replicate) 생성 — 월별 쿼터."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models.image_avatar_quota import UserMonthlyAvatarQuota, WorldMonthlyAvatarQuota
from ..db.models.world import World
from ..utils.config import Settings


def _utc_year_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def assert_npc_avatar_quota_allows(
    db: Session,
    *,
    user_id: uuid.UUID,
    world_id: uuid.UUID,
    settings: Settings,
) -> None:
    ym = _utc_year_month()
    user_limit = max(0, int(settings.image_gen_npc_per_user_monthly))
    world_limit = max(0, int(settings.image_gen_npc_per_world_monthly))

    urow = db.scalars(
        select(UserMonthlyAvatarQuota).where(
            UserMonthlyAvatarQuota.user_id == user_id,
            UserMonthlyAvatarQuota.year_month == ym,
        )
    ).first()
    ucount = int(urow.generation_count) if urow is not None else 0
    if user_limit > 0 and ucount >= user_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"이번 달 NPC 초상 생성 한도({user_limit}회)에 도달했습니다.",
        )

    wrow = db.scalars(
        select(WorldMonthlyAvatarQuota).where(
            WorldMonthlyAvatarQuota.world_id == world_id,
            WorldMonthlyAvatarQuota.year_month == ym,
        )
    ).first()
    wcount = int(wrow.generation_count) if wrow is not None else 0
    if world_limit > 0 and wcount >= world_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"이 월드의 이번 달 NPC 초상 생성 한도({world_limit}회)에 도달했습니다."
            ),
        )


def persist_npc_avatar_generation(
    db: Session,
    *,
    user_id: uuid.UUID,
    world_id: uuid.UUID,
    image_url: str,
    world_row: World,
    npc_id: str,
    settings: Settings,
) -> None:
    _ = settings
    ym = _utc_year_month()

    urow = db.scalars(
        select(UserMonthlyAvatarQuota).where(
            UserMonthlyAvatarQuota.user_id == user_id,
            UserMonthlyAvatarQuota.year_month == ym,
        )
    ).first()
    if urow is None:
        urow = UserMonthlyAvatarQuota(user_id=user_id, year_month=ym, generation_count=0)
        db.add(urow)
        db.flush()

    war = db.scalars(
        select(WorldMonthlyAvatarQuota).where(
            WorldMonthlyAvatarQuota.world_id == world_id,
            WorldMonthlyAvatarQuota.year_month == ym,
        )
    ).first()
    if war is None:
        war = WorldMonthlyAvatarQuota(world_id=world_id, year_month=ym, generation_count=0)
        db.add(war)
        db.flush()

    urow.generation_count = int(urow.generation_count) + 1
    war.generation_count = int(war.generation_count) + 1

    chars = world_row.characters_data if isinstance(world_row.characters_data, dict) else {}
    npcs = chars.get("npcs")
    if not isinstance(npcs, list):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="characters.npcs must be a list",
        )
    new_npcs: list[object] = []
    found = False
    for raw in npcs:
        if isinstance(raw, dict) and str(raw.get("id", "")) == npc_id:
            d = dict(raw)
            d["portrait_image_url"] = image_url
            new_npcs.append(d)
            found = True
        else:
            new_npcs.append(raw)
    if not found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NPC not found",
        )
    world_row.characters_data = {**chars, "npcs": new_npcs}
    db.add(world_row)
    db.flush()


def remaining_npc_avatar_quota(
    db: Session,
    *,
    user_id: uuid.UUID,
    world_id: uuid.UUID,
    settings: Settings,
) -> tuple[int | None, int | None]:
    ym = _utc_year_month()
    user_limit = max(0, int(settings.image_gen_npc_per_user_monthly))
    world_limit = max(0, int(settings.image_gen_npc_per_world_monthly))

    urow = db.scalars(
        select(UserMonthlyAvatarQuota).where(
            UserMonthlyAvatarQuota.user_id == user_id,
            UserMonthlyAvatarQuota.year_month == ym,
        )
    ).first()
    ucount = int(urow.generation_count) if urow is not None else 0
    war = db.scalars(
        select(WorldMonthlyAvatarQuota).where(
            WorldMonthlyAvatarQuota.world_id == world_id,
            WorldMonthlyAvatarQuota.year_month == ym,
        )
    ).first()
    wcount = int(war.generation_count) if war is not None else 0

    u_rem: int | None = None if user_limit <= 0 else max(0, user_limit - ucount)
    w_rem: int | None = None if world_limit <= 0 else max(0, world_limit - wcount)
    return u_rem, w_rem
