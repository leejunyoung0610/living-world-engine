"""플랫폼 일일 비용 집계·웹훅 (Epic E)."""

from __future__ import annotations

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
    assert abs(row.cost_usd - 0.03) < 1e-9


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
