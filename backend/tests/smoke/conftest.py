"""스모크: Stub GameEngine + 인메모리 SQLite (유닛 test_api_play 와 동일 전제)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.src.db.base import Base
from backend.src.db.models import (  # noqa: F401 — metadata
    PlatformCostDaily,
    PlaySession,
    User,
    UserDailyTurnUsage,
    World,
)
from backend.src.db.session import get_db
from backend.src.main import create_app
from backend.src.services.play_session_db import delete_all_play_sessions
from backend.src.services.play_sessions import clear_all_sessions
from backend.tests.unit.test_api_play import MIN_CHARS, MIN_WORLD, StubGameEngine


@pytest.fixture
def smoke_api_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-smoke-ci-placeholder")
    monkeypatch.setattr("backend.src.api.routes.play.GameEngine", StubGameEngine)

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    clear_all_sessions()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        clear_all_sessions()
        cleanup = TestSessionLocal()
        try:
            delete_all_play_sessions(cleanup)
        finally:
            cleanup.close()


__all__ = ["MIN_CHARS", "MIN_WORLD", "smoke_api_client"]
