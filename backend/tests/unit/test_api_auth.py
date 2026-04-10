"""인증 API — SQLite(테스트) + JWT."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.src.db.base import Base
from backend.src.db.models import InviteCode, User  # noqa: F401 — metadata 등록
from backend.src.db.session import get_db
from backend.src.main import create_app


@pytest.fixture
def client() -> TestClient:
    # :memory: 는 연결마다 별도 DB → 풀/스레드에서 테이블 소실 방지
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


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_signup_login_me_flow(client: TestClient) -> None:
    r = client.post(
        "/api/auth/signup",
        json={
            "email": "a@example.com",
            "username": "Tester",
            "password": "password123",
            "invite_code": "",
        },
    )
    assert r.status_code == 201

    r = client.post(
        "/api/auth/login",
        json={"email": "a@example.com", "password": "password123"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    token = data["access_token"]
    r = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json() == {"email": "a@example.com", "username": "Tester"}


def test_signup_duplicate(client: TestClient) -> None:
    body = {
        "email": "b@example.com",
        "username": "B",
        "password": "password123",
        "invite_code": "ANY",
    }
    assert client.post("/api/auth/signup", json=body).status_code == 201
    r = client.post("/api/auth/signup", json=body)
    assert r.status_code == 409


def test_me_without_token(client: TestClient) -> None:
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def _client_with_db_and_env(monkeypatch: pytest.MonkeyPatch, **env: str):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
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
    client = TestClient(app)
    return client, TestSessionLocal


def test_signup_invite_required_empty_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REQUIRE_INVITE_CODE_FOR_SIGNUP", "true")
    client, _ = _client_with_db_and_env(monkeypatch)
    try:
        r = client.post(
            "/api/auth/signup",
            json={
                "email": "inv@example.com",
                "username": "I",
                "password": "password123",
                "invite_code": "",
            },
        )
        assert r.status_code == 422
        assert r.json()["detail"] == "초대 코드를 입력해 주세요."
    finally:
        client.app.dependency_overrides.clear()


def test_signup_invite_required_valid_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REQUIRE_INVITE_CODE_FOR_SIGNUP", "true")
    client, SessionLocal = _client_with_db_and_env(monkeypatch)
    try:
        db = SessionLocal()
        db.add(InviteCode(code="beta-1", max_uses=1, uses_count=0))
        db.commit()
        db.close()

        r = client.post(
            "/api/auth/signup",
            json={
                "email": "ok@example.com",
                "username": "Ok",
                "password": "password123",
                "invite_code": "BETA-1",
            },
        )
        assert r.status_code == 201

        db = SessionLocal()
        inv = db.scalars(select(InviteCode).where(InviteCode.code == "beta-1")).one()
        assert inv.uses_count == 1
        db.close()
    finally:
        client.app.dependency_overrides.clear()


def test_signup_invite_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REQUIRE_INVITE_CODE_FOR_SIGNUP", "true")
    client, SessionLocal = _client_with_db_and_env(monkeypatch)
    try:
        db = SessionLocal()
        db.add(InviteCode(code="once", max_uses=1, uses_count=0))
        db.commit()
        db.close()

        assert (
            client.post(
                "/api/auth/signup",
                json={
                    "email": "u1@example.com",
                    "username": "U1",
                    "password": "password123",
                    "invite_code": "once",
                },
            ).status_code
            == 201
        )
        r = client.post(
            "/api/auth/signup",
            json={
                "email": "u2@example.com",
                "username": "U2",
                "password": "password123",
                "invite_code": "once",
            },
        )
        assert r.status_code == 403
        assert "더 이상 사용할 수 없습니다" in r.json()["detail"]
    finally:
        client.app.dependency_overrides.clear()


def test_signup_max_total_users(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_TOTAL_USERS", "1")
    client, _ = _client_with_db_and_env(monkeypatch)
    try:
        assert (
            client.post(
                "/api/auth/signup",
                json={
                    "email": "first@example.com",
                    "username": "F",
                    "password": "password123",
                    "invite_code": "",
                },
            ).status_code
            == 201
        )
        r = client.post(
            "/api/auth/signup",
            json={
                "email": "second@example.com",
                "username": "S",
                "password": "password123",
                "invite_code": "",
            },
        )
        assert r.status_code == 403
        assert "가득" in r.json()["detail"]
    finally:
        client.app.dependency_overrides.clear()
