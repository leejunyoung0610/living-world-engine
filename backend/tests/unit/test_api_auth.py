"""인증 API — SQLite(테스트) + JWT."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.src.db.base import Base
from backend.src.db.models import User  # noqa: F401 — Base.metadata에 users 테이블 등록
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
