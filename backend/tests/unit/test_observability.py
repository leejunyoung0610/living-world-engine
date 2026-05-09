"""Epic H — 구조화 액세스 로그, Sentry 연동 훅."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.src.db.base import Base
from backend.src.db.models import InviteCode, User  # noqa: F401
from backend.src.db.session import get_db
from backend.src.main import create_app
from backend.src.utils.logging_setup import JsonLogFormatter


@pytest.fixture
def memory_db_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STRUCTURED_LOGGING", "true")
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
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_structured_access_log_fields_and_x_request_id(
    memory_db_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("INFO", logger="living_world.access"):
        r = memory_db_client.get("/health")
    assert r.status_code == 200
    rid = r.headers.get("X-Request-Id")
    assert rid
    access = [rec for rec in caplog.records if rec.name == "living_world.access"]
    assert access
    last = access[-1]
    assert getattr(last, "request_id", None) == rid
    assert getattr(last, "path", None) == "/health"
    assert getattr(last, "status_code", None) == 200
    assert getattr(last, "http_method", None) == "GET"


def test_json_formatter_includes_request_fields() -> None:
    import logging

    record = logging.LogRecord(
        name="test_json",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request",
        args=(),
        exc_info=None,
    )
    record.request_id = "abc"
    record.http_method = "POST"
    record.path = "/x"
    record.status_code = 201
    record.duration_ms = 1.23
    line = JsonLogFormatter().format(record)
    data = json.loads(line)
    assert data["path"] == "/x"
    assert data["status_code"] == 201
    assert data["request_id"] == "abc"


def test_unhandled_exception_calls_capture_exception(mocker: pytest.MockerFixture) -> None:
    mock_capture = mocker.patch("backend.src.api.error_handlers.sentry_sdk.capture_exception")
    app = create_app()

    @app.get("/_crash_epic_h")
    def _crash_epic_h() -> None:
        raise RuntimeError("epic_h")

    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get("/_crash_epic_h")
    assert r.status_code == 500
    mock_capture.assert_called_once()
