"""인증 API — 인메모리 저장소 + JWT."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.src.main import create_app
from backend.src.services import auth_store


@pytest.fixture
def client() -> TestClient:
    auth_store.clear()
    return TestClient(create_app())


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
