"""slowapi 레이트 리밋이 실제로 적용되는지 검증 (Epic F).

다른 테스트는 `conftest.py` 가 ``RATE_LIMITING_ENABLED=false`` 로 끈다.
여기서는 ``@pytest.mark.rate_limit`` 으로 한도를 켜고 429 를 확인한다.
"""

from __future__ import annotations

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.src.api.limiter import limiter
from backend.src.db.base import Base
from backend.src.db.models import InviteCode, User  # noqa: F401 — metadata 등록
from backend.src.db.session import get_db
from backend.src.main import create_app

pytestmark = pytest.mark.rate_limit

LOGIN_LIMIT_PER_MINUTE = 30  # auth.login 의 @limiter.limit("30/minute")

#: (메서드, 경로) — slowapi 래퍼(`__wrapped__`)가 라우터에 등록돼 있어야 하는 엔드포인트
RATE_LIMITED_ROUTES = {
    ("POST", "/api/auth/signup"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/play/{session_id}/turn"),
    ("POST", "/api/play/{session_id}/turn/stream"),
    ("POST", "/api/play/{session_id}/turn/regenerate/stream"),
    ("POST", "/api/worlds/{world_id}/generate-cover"),
    ("POST", "/api/worlds/{world_id}/npcs/{npc_id}/generate-portrait"),
}


@pytest.fixture
def limited_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("RATE_LIMITING_ENABLED", "true")
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
    assert limiter.enabled is True
    app.dependency_overrides[get_db] = override_get_db
    limiter.reset()  # 모듈 싱글톤 — 이전 테스트의 카운터 제거
    try:
        yield TestClient(app)
    finally:
        limiter.reset()
        limiter.enabled = False
        app.dependency_overrides.clear()


def test_login_returns_429_after_limit(limited_client: TestClient) -> None:
    body = {"email": "nobody@example.com", "password": "wrong-password"}
    for i in range(LOGIN_LIMIT_PER_MINUTE):
        r = limited_client.post("/api/auth/login", json=body)
        assert r.status_code == 401, f"request {i + 1}: {r.status_code} {r.text}"

    r = limited_client.post("/api/auth/login", json=body)
    assert r.status_code == 429
    assert "잠시 후" in r.json()["detail"]


def test_limit_is_per_route(limited_client: TestClient) -> None:
    """로그인 한도 소진이 다른 엔드포인트(가입)까지 막지 않는다."""
    body = {"email": "nobody@example.com", "password": "wrong-password"}
    for _ in range(LOGIN_LIMIT_PER_MINUTE + 1):
        limited_client.post("/api/auth/login", json=body)

    r = limited_client.post(
        "/api/auth/signup",
        json={
            "email": "fresh@example.com",
            "username": "Fresh",
            "password": "password123",
            "invite_code": "",
        },
    )
    assert r.status_code == 201, r.text


def test_rate_limited_endpoints_are_registered_wrapped() -> None:
    """데코레이터 순서 회귀 방지 — 라우터가 slowapi 래퍼를 등록했는지 확인."""
    app = create_app()
    registered = {
        (method, route.path): route.endpoint
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }
    for key in RATE_LIMITED_ROUTES:
        assert key in registered, f"route missing: {key}"
        assert hasattr(registered[key], "__wrapped__"), f"rate limit not applied: {key}"
