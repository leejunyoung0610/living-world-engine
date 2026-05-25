"""이미지 생성 일일 예산·집계 (커버 + NPC 초상 공통 UTC 일자 풀)."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models.image_gen_cost_daily import ImageGenCostDaily
from ..utils.config import Settings

logger = logging.getLogger(__name__)


def utc_usage_date() -> date:
    return datetime.now(timezone.utc).date()


def assert_image_gen_daily_budget_allows(db: Session, settings: Settings) -> None:
    """``image_gen_daily_budget_usd`` 가 설정된 경우, 커버 1건 분의 추정 비용이 넘으면 차단."""
    _assert_daily_budget_allows(
        db,
        settings,
        float(settings.image_gen_cover_cost_estimate_usd),
    )


def assert_npc_avatar_daily_budget_allows(db: Session, settings: Settings) -> None:
    """동일 일 예산 풀에 대해 NPC 초상 1건 추정 비용 검사."""
    _assert_daily_budget_allows(
        db,
        settings,
        float(settings.image_npc_avatar_cost_estimate_usd),
    )


def _assert_daily_budget_allows(
    db: Session,
    settings: Settings,
    incremental_estimate_usd: float,
) -> None:
    budget = settings.image_gen_daily_budget_usd
    if budget is None or float(budget) <= 0:
        return
    est = float(incremental_estimate_usd)
    if est <= 0:
        return

    today = utc_usage_date()
    row = db.scalars(
        select(ImageGenCostDaily).where(ImageGenCostDaily.usage_date == today),
    ).first()
    prev = float(row.cost_usd) if row is not None else 0.0
    lim = float(budget)

    if prev + est > lim + 1e-9:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"오늘(UTC 기준) 이미지 생성 추정 예산(${lim:.2f})을 초과합니다. "
                "내일 다시 시도하거나 설정을 확인하세요."
            ),
        )


def record_cover_generation_usage(db: Session, settings: Settings) -> None:
    """커버 1건 성공 후 호출."""
    est = float(settings.image_gen_cover_cost_estimate_usd)
    today = utc_usage_date()
    row = db.scalars(
        select(ImageGenCostDaily).where(ImageGenCostDaily.usage_date == today),
    ).first()
    if row is None:
        row = ImageGenCostDaily(
            usage_date=today,
            cost_usd=0.0,
            cover_generation_count=0,
            npc_avatar_generation_count=0,
            alert_sent=False,
        )
        db.add(row)
        db.flush()

    row.cover_generation_count = int(row.cover_generation_count) + 1
    if est > 0:
        row.cost_usd = float(row.cost_usd) + est
    db.flush()

    _maybe_fire_daily_image_budget_alert(db, row, today, settings)


def record_npc_avatar_generation_usage(db: Session, settings: Settings) -> None:
    """NPC 초상 1건 성공 후 호출."""
    est = float(settings.image_npc_avatar_cost_estimate_usd)
    today = utc_usage_date()
    row = db.scalars(
        select(ImageGenCostDaily).where(ImageGenCostDaily.usage_date == today),
    ).first()
    if row is None:
        row = ImageGenCostDaily(
            usage_date=today,
            cost_usd=0.0,
            cover_generation_count=0,
            npc_avatar_generation_count=0,
            alert_sent=False,
        )
        db.add(row)
        db.flush()

    row.npc_avatar_generation_count = int(row.npc_avatar_generation_count) + 1
    if est > 0:
        row.cost_usd = float(row.cost_usd) + est
    db.flush()

    _maybe_fire_daily_image_budget_alert(db, row, today, settings)


def _maybe_fire_daily_image_budget_alert(
    db: Session,
    row: ImageGenCostDaily,
    today: date,
    settings: Settings,
) -> None:
    budget_thr = settings.image_gen_daily_budget_usd
    webhook = settings.platform_cost_alert_webhook_url.strip()

    cost_now = float(row.cost_usd)
    if (
        budget_thr is None
        or float(budget_thr) <= 0
        or cost_now < float(budget_thr)
        or row.alert_sent
        or not webhook
    ):
        return

    cov = int(row.cover_generation_count)
    npc_n = int(row.npc_avatar_generation_count)
    payload = {
        "text": (
            "[Living World Engine] 이미지 생성 일일 추정 비용이 예산 임계에 도달했습니다. "
            f"UTC {today.isoformat()} 추정 합계 ${cost_now:.4f} USD · "
            f"커버 {cov}건 · NPC 초상 {npc_n}건 · 예산 ${float(budget_thr):.2f} USD."
        )
    }
    try:
        req = urllib.request.Request(
            webhook,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=12)
    except (urllib.error.URLError, OSError) as e:
        logger.warning("image gen cost webhook failed: %s", e)
    row.alert_sent = True
    db.flush()
