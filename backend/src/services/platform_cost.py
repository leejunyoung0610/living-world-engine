"""플랫폼 키 턴 추정 비용 일일 집계·웹훅 알림 (Epic E).

임계 초과 시 **알림만** 보낸다(LLM 호출을 자동으로 막지 않음). 플레이를 멈추려면
운영자가 ``EMERGENCY_SHUTDOWN=true`` 로 수동 셧다운한다.

집계는 ``UPDATE ... SET cost_usd = cost_usd + :delta`` 로 DB 안에서 더하고(동시 턴의
갱신 유실 방지), 알림은 ``alert_sent = false`` 조건부 UPDATE 로 보낼 권리를 한 요청만 얻는다.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import date, datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..db.atomic import NO_SYNC, insert_ignore
from ..db.models import PlatformCostDaily
from ..db.types import to_money
from ..utils.config import Settings

logger = logging.getLogger(__name__)


def utc_usage_date() -> date:
    return datetime.now(timezone.utc).date()


def record_platform_cost_delta(db: Session, delta_usd: float, settings: Settings) -> None:
    """`delta_usd` 를 오늘(UTC) 행에 원자적으로 가산. 임계 이상이면 웹훅 1회.

    commit 은 호출자(턴 영속화)가 한다 — 같은 트랜잭션에 묶인다.
    """
    if delta_usd <= 0:
        return
    amount = to_money(delta_usd)
    if amount <= 0:  # 1e-6 USD 미만은 컬럼 스케일에서 0
        return

    today = utc_usage_date()
    insert_ignore(
        db,
        PlatformCostDaily,
        {"usage_date": today, "cost_usd": to_money(0), "alert_sent": False},
    )
    db.execute(
        update(PlatformCostDaily)
        .where(PlatformCostDaily.usage_date == today)
        .values(cost_usd=PlatformCostDaily.cost_usd + amount)
        .execution_options(**NO_SYNC)
    )

    thr = settings.platform_daily_cost_alert_threshold_usd
    webhook = settings.platform_cost_alert_webhook_url.strip()
    if thr is None or not webhook:
        return

    claimed = db.execute(
        update(PlatformCostDaily)
        .where(
            PlatformCostDaily.usage_date == today,
            PlatformCostDaily.alert_sent.is_(False),
            PlatformCostDaily.cost_usd >= to_money(thr),
        )
        .values(alert_sent=True)
        .execution_options(**NO_SYNC)
    )
    if claimed.rowcount != 1:
        return

    total = db.scalar(
        select(PlatformCostDaily.cost_usd).where(PlatformCostDaily.usage_date == today)
    )
    payload = {
        "text": (
            f"[Living World Engine] 플랫폼 일일 추정 비용 {float(total or 0):.4f} USD "
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
