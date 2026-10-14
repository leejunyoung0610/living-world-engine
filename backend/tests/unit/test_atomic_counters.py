"""동시 요청에서 턴 쿼터·비용 집계가 원자적인지 — 실제 커넥션 여러 개 + 스레드.

- SQLite(파일 DB): 항상 실행.
- PostgreSQL: ``LWE_TEST_POSTGRES_URL`` 이 있으면 임시 스키마를 만들어 실행 후 삭제
  (예: ``LWE_TEST_POSTGRES_URL=postgresql://postgres@127.0.0.1:5432/living_world_test``).
"""

from __future__ import annotations

import os
import threading
import uuid
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.src.db.base import Base
from backend.src.db.models import PlatformCostDaily, User, UserDailyTurnUsage
from backend.src.services import platform_cost, turn_quota
from backend.src.utils.config import Settings

THREADS = 12
TURN_LIMIT = 5
_TABLES = [User.__table__, UserDailyTurnUsage.__table__, PlatformCostDaily.__table__]


def _sqlite_engine(tmp_path: Path) -> Iterator[Engine]:
    eng = create_engine(
        f"sqlite:///{tmp_path / 'atomic.sqlite'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(eng, tables=_TABLES)
    try:
        yield eng
    finally:
        eng.dispose()


def _postgres_engine(url: str) -> Iterator[Engine]:
    schema = f"lwe_atomic_{uuid.uuid4().hex[:10]}"
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    eng = create_engine(
        url,
        connect_args={"options": f"-csearch_path={schema}"},
        pool_size=THREADS + 2,
    )
    try:
        Base.metadata.create_all(eng, tables=_TABLES)
        yield eng
    finally:
        eng.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture(params=["sqlite", "postgresql"])
def engine(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[Engine]:
    if request.param == "sqlite":
        yield from _sqlite_engine(tmp_path)
        return
    url = os.environ.get("LWE_TEST_POSTGRES_URL", "").strip()
    if not url:
        pytest.skip("LWE_TEST_POSTGRES_URL 미설정 — PostgreSQL 동시성 테스트 생략")
    yield from _postgres_engine(url)


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def _make_user(SessionLocal: sessionmaker[Session]) -> User:
    with SessionLocal() as s:
        u = User(email=f"{uuid.uuid4().hex[:8]}@example.com", username="racer")
        s.add(u)
        s.commit()
        s.refresh(u)
        s.expunge(u)
        return u


def _run_concurrently(fn, n: int = THREADS) -> list[BaseException | None]:
    barrier = threading.Barrier(n)
    results: list[BaseException | None] = [None] * n

    def worker(i: int) -> None:
        barrier.wait()
        try:
            fn()
        except BaseException as e:  # noqa: BLE001 — 스레드 결과로 수집
            results[i] = e

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    return results


def test_concurrent_turn_reservations_never_exceed_limit(
    session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ENFORCE_PLATFORM_TURN_QUOTA", "true")
    monkeypatch.setenv("PLATFORM_DAILY_TURN_LIMIT", str(TURN_LIMIT))
    settings = Settings()
    user = _make_user(session_factory)

    def reserve() -> None:
        with session_factory() as s:
            turn_quota.reserve_platform_turn(s, user.id, settings)

    results = _run_concurrently(reserve)
    ok = [r for r in results if r is None]
    rejected = [r for r in results if isinstance(r, HTTPException) and r.status_code == 429]
    assert len(ok) == TURN_LIMIT
    assert len(rejected) == THREADS - TURN_LIMIT, [r for r in results if r is not None]

    with session_factory() as s:
        count = s.scalar(
            select(UserDailyTurnUsage.turn_count).where(UserDailyTurnUsage.user_id == user.id)
        )
    assert count == TURN_LIMIT


def test_concurrent_cost_deltas_are_not_lost(
    session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PLATFORM_DAILY_COST_ALERT_THRESHOLD_USD", raising=False)
    settings = Settings()

    def add_cost() -> None:
        with session_factory() as s:
            platform_cost.record_platform_cost_delta(s, 0.012345, settings)
            s.commit()

    results = _run_concurrently(add_cost)
    assert results == [None] * THREADS

    with session_factory() as s:
        total = s.scalar(select(PlatformCostDaily.cost_usd))
    assert total == Decimal("0.012345") * THREADS
