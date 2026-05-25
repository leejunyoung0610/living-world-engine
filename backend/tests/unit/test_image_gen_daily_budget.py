"""커버 이미지 일 예산 추적·웹훅."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.src.db.base import Base
from backend.src.db.models import ImageGenCostDaily  # noqa: F401
from backend.src.services.image_gen_daily_budget import (
    assert_image_gen_daily_budget_allows,
    assert_npc_avatar_daily_budget_allows,
    record_cover_generation_usage,
    record_npc_avatar_generation_usage,
    utc_usage_date,
)
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


def test_record_accumulates_cost_and_count(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IMAGE_GEN_COVER_COST_ESTIMATE_USD", "0.02")
    s = Settings()
    record_cover_generation_usage(db_session, s)
    record_cover_generation_usage(db_session, s)
    row = db_session.scalars(
        select(ImageGenCostDaily).where(ImageGenCostDaily.usage_date == utc_usage_date()),
    ).one()
    assert row.cover_generation_count == 2
    assert abs(float(row.cost_usd) - 0.04) < 1e-9


def test_assert_blocks_when_next_exceeds_budget(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IMAGE_GEN_DAILY_BUDGET_USD", "0.04")
    monkeypatch.setenv("IMAGE_GEN_COVER_COST_ESTIMATE_USD", "0.04")
    record_cover_generation_usage(db_session, Settings())

    with pytest.raises(HTTPException) as ei:
        assert_image_gen_daily_budget_allows(db_session, Settings())
    assert ei.value.status_code == 429


def test_webhook_when_hits_budget(monkeypatch: pytest.MonkeyPatch, db_session) -> None:
    monkeypatch.setenv("IMAGE_GEN_DAILY_BUDGET_USD", "0.04")
    monkeypatch.setenv("IMAGE_GEN_COVER_COST_ESTIMATE_USD", "0.04")
    monkeypatch.setenv("PLATFORM_COST_ALERT_WEBHOOK_URL", "https://hooks.example/webhook")
    s = Settings()
    with patch("urllib.request.urlopen") as mo:
        record_cover_generation_usage(db_session, s)
    mo.assert_called_once()
    row = db_session.scalars(
        select(ImageGenCostDaily).where(ImageGenCostDaily.usage_date == utc_usage_date()),
    ).one()
    assert row.alert_sent is True


def test_npc_avatar_record_and_share_daily_budget_pool(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IMAGE_NPC_AVATAR_COST_ESTIMATE_USD", "0.01")
    record_npc_avatar_generation_usage(db_session, Settings())
    row = db_session.scalars(
        select(ImageGenCostDaily).where(ImageGenCostDaily.usage_date == utc_usage_date()),
    ).one()
    assert int(row.npc_avatar_generation_count) == 1
    assert abs(float(row.cost_usd) - 0.01) < 1e-9


def test_assert_npc_budget_blocks(monkeypatch: pytest.MonkeyPatch, db_session) -> None:
    monkeypatch.setenv("IMAGE_GEN_DAILY_BUDGET_USD", "0.01")
    monkeypatch.setenv("IMAGE_NPC_AVATAR_COST_ESTIMATE_USD", "0.01")
    record_npc_avatar_generation_usage(db_session, Settings())

    with pytest.raises(HTTPException) as ei:
        assert_npc_avatar_daily_budget_allows(db_session, Settings())
    assert ei.value.status_code == 429


def test_no_webhook_second_record(monkeypatch: pytest.MonkeyPatch, db_session) -> None:
    monkeypatch.setenv("IMAGE_GEN_DAILY_BUDGET_USD", "0.04")
    monkeypatch.setenv("IMAGE_GEN_COVER_COST_ESTIMATE_USD", "0.02")
    monkeypatch.setenv("PLATFORM_COST_ALERT_WEBHOOK_URL", "https://hooks.example/webhook")
    s = Settings()
    with patch("urllib.request.urlopen") as m1:
        record_cover_generation_usage(db_session, s)
        record_cover_generation_usage(db_session, s)
    assert m1.call_count == 1
