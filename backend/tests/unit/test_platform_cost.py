"""플랫폼 일일 비용 집계·웹훅 (Epic E)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.src.db.base import Base
from backend.src.db.models import PlatformCostDaily  # noqa: F401
from backend.src.services.platform_cost import record_platform_cost_delta, utc_usage_date
from backend.src.utils.config import Settings


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        yield s
    finally:
        s.close()


def test_record_platform_cost_accumulates(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATFORM_DAILY_COST_ALERT_THRESHOLD_USD", "99999")
    s = Settings()
    record_platform_cost_delta(db_session, 0.01, s)
    record_platform_cost_delta(db_session, 0.02, s)
    row = db_session.scalars(
        select(PlatformCostDaily).where(PlatformCostDaily.usage_date == utc_usage_date()),
    ).one()
    assert row.cost_usd == Decimal("0.03")


def test_webhook_once_when_over_threshold(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATFORM_DAILY_COST_ALERT_THRESHOLD_USD", "0.05")
    monkeypatch.setenv("PLATFORM_COST_ALERT_WEBHOOK_URL", "https://example.com/hook")
    s = Settings()
    with patch("urllib.request.urlopen") as m_open:
        record_platform_cost_delta(db_session, 0.04, s)
        record_platform_cost_delta(db_session, 0.02, s)
    assert m_open.call_count == 1
    row = db_session.scalars(
        select(PlatformCostDaily).where(PlatformCostDaily.usage_date == utc_usage_date()),
    ).one()
    assert row.alert_sent is True
    with patch("urllib.request.urlopen") as m2:
        record_platform_cost_delta(db_session, 0.1, s)
    assert m2.call_count == 0


def test_cost_accumulates_without_float_drift(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    """Numeric(12,6) + DB 내 가산 — 0.1 을 세 번 더하면 정확히 0.3 (float 이면 0.30000000000000004)."""
    monkeypatch.delenv("PLATFORM_DAILY_COST_ALERT_THRESHOLD_USD", raising=False)
    s = Settings()
    for _ in range(3):
        record_platform_cost_delta(db_session, 0.1, s)
    db_session.commit()
    db_session.expire_all()
    total = db_session.scalar(
        select(PlatformCostDaily.cost_usd).where(PlatformCostDaily.usage_date == utc_usage_date())
    )
    assert total == Decimal("0.3")


def test_no_webhook_without_url_even_over_threshold(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """임계 초과여도 웹훅 URL 이 없으면 알림 플래그를 소모하지 않는다 (나중에 URL 설정 시 1회 발송)."""
    monkeypatch.setenv("PLATFORM_DAILY_COST_ALERT_THRESHOLD_USD", "0.01")
    monkeypatch.delenv("PLATFORM_COST_ALERT_WEBHOOK_URL", raising=False)
    with patch("urllib.request.urlopen") as m_open:
        record_platform_cost_delta(db_session, 0.05, Settings())
    assert m_open.call_count == 0
    row = db_session.scalars(
        select(PlatformCostDaily).where(PlatformCostDaily.usage_date == utc_usage_date()),
    ).one()
    assert row.alert_sent is False
