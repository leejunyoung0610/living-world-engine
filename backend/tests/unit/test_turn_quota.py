"""플랫폼 턴 쿼터 정책 단위 테스트."""

from __future__ import annotations

import pytest

from backend.src.services.turn_quota import platform_quota_enforced, utc_usage_date
from backend.src.utils.config import Settings


def test_utc_usage_date_is_today_utc() -> None:
    from datetime import datetime, timezone

    assert utc_usage_date() == datetime.now(timezone.utc).date()


@pytest.fixture
def settings_on(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("ENFORCE_PLATFORM_TURN_QUOTA", "true")
    monkeypatch.setenv("PLATFORM_DAILY_TURN_LIMIT", "20")
    return Settings()


def test_platform_quota_enforced_when_config_on(settings_on: Settings) -> None:
    assert platform_quota_enforced(settings_on) is True


def test_platform_quota_off_when_limit_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENFORCE_PLATFORM_TURN_QUOTA", "true")
    monkeypatch.setenv("PLATFORM_DAILY_TURN_LIMIT", "0")
    s = Settings()
    assert platform_quota_enforced(s) is False
