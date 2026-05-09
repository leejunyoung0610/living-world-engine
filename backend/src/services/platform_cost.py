"""플랫폼 키 턴 추정 비용 일일 집계·웹훅 알림 (Epic E)."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import PlatformCostDaily
from ..utils.config import Settings

logger = logging.getLogger(__name__)


def utc_usage_date() -> date:
    return datetime.now(timezone.utc).date()


def record_platform_cost_delta(db: Session, delta_usd: float, settings: Settings) -> None:
    """`delta_usd` 를 오늘(UTC) 행에 가산. 임계 초과 시 웹훅 1회."""
    if delta_usd <= 0:
        return
    thr = settings.platform_daily_cost_alert_threshold_usd
    webhook = settings.platform_cost_alert_webhook_url.strip()

    today = utc_usage_date()
    row = db.scalars(
        select(PlatformCostDaily).where(PlatformCostDaily.usage_date == today),
    ).first()
    if row is None:
        row = PlatformCostDaily(usage_date=today, cost_usd=0.0, alert_sent=False)
        db.add(row)
    row.cost_usd = float(row.cost_usd) + float(delta_usd)
    db.flush()

    if (
        thr is not None
        and float(row.cost_usd) >= float(thr)
        and not row.alert_sent
        and webhook
    ):
        payload = {
            "text": (
                f"[Living World Engine] 플랫폼 일일 추정 비용 {float(row.cost_usd):.4f} USD "
                f"(임계 {float(thr):.2f} USD). UTC 기준일 {today.isoformat()}."
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
            logger.warning("platform cost webhook failed: %s", e)
        row.alert_sent = True
        db.flush()
