"""이미지 생성 일일 예산·집계 (커버 + NPC 초상 공통 UTC 일자 풀)."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..db.atomic import NO_SYNC, insert_ignore
from ..db.models.image_gen_cost_daily import ImageGenCostDaily
from ..db.types import to_money
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
    prev_cost = db.scalar(
        select(ImageGenCostDaily.cost_usd).where(ImageGenCostDaily.usage_date == today),
    )
    prev = float(prev_cost) if prev_cost is not None else 0.0
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
    _record_image_generation(
        db,
        settings,
        ImageGenCostDaily.cover_generation_count,
        float(settings.image_gen_cover_cost_estimate_usd),
    )


def record_npc_avatar_generation_usage(db: Session, settings: Settings) -> None:
    """NPC 초상 1건 성공 후 호출."""
    _record_image_generation(
        db,
        settings,
        ImageGenCostDaily.npc_avatar_generation_count,
        float(settings.image_npc_avatar_cost_estimate_usd),
    )


def _record_image_generation(
    db: Session,
    settings: Settings,
    count_column: Any,
    est_usd: float,
) -> None:
    """오늘(UTC) 행에 건수 +1·추정 비용 가산 — DB 안에서 원자적으로 (``col = col + :delta``)."""
    today = utc_usage_date()
    insert_ignore(
        db,
        ImageGenCostDaily,
        {
            "usage_date": today,
            "cost_usd": to_money(0),
            "cover_generation_count": 0,
            "npc_avatar_generation_count": 0,
            "alert_sent": False,
        },
    )
    values: dict[Any, Any] = {count_column: count_column + 1}
    if est_usd > 0:
        values[ImageGenCostDaily.cost_usd] = ImageGenCostDaily.cost_usd + to_money(est_usd)
    db.execute(
        update(ImageGenCostDaily)
        .where(ImageGenCostDaily.usage_date == today)
        .values(values)
        .execution_options(**NO_SYNC)
    )

    _maybe_fire_daily_image_budget_alert(db, today, settings)


def _maybe_fire_daily_image_budget_alert(
    db: Session,
    today: date,
    settings: Settings,
) -> None:
    budget_thr = settings.image_gen_daily_budget_usd
    webhook = settings.platform_cost_alert_webhook_url.strip()
    if budget_thr is None or float(budget_thr) <= 0 or not webhook:
        return

    # 임계 도달 + 미발송일 때만 한 요청이 알림 권리를 얻는다 (조건부 UPDATE).
    claimed = db.execute(
        update(ImageGenCostDaily)
        .where(
            ImageGenCostDaily.usage_date == today,
            ImageGenCostDaily.alert_sent.is_(False),
            ImageGenCostDaily.cost_usd >= to_money(budget_thr),
        )
        .values(alert_sent=True)
        .execution_options(**NO_SYNC)
    )
    if claimed.rowcount != 1:
        return

    cost_now, cov, npc_n = db.execute(
        select(
            ImageGenCostDaily.cost_usd,
            ImageGenCostDaily.cover_generation_count,
            ImageGenCostDaily.npc_avatar_generation_count,
        ).where(ImageGenCostDaily.usage_date == today)
    ).one()
    payload = {
        "text": (
            "[Living World Engine] 이미지 생성 일일 추정 비용이 예산 임계에 도달했습니다. "
            f"UTC {today.isoformat()} 추정 합계 ${float(cost_now):.4f} USD · "
            f"커버 {int(cov)}건 · NPC 초상 {int(npc_n)}건 · 예산 ${float(budget_thr):.2f} USD."
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
