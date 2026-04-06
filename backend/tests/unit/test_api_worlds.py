"""월드 CRUD API — SQLite + JWT."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.src.db.base import Base
from backend.src.db.models import User, World  # noqa: F401
from backend.src.db.session import get_db
from backend.src.main import create_app

MIN_WORLD = {
    "id": "ugc_test",
    "name": "테스트 월드",
    "description": "d",
    "time": "t1",
    "regions": [],
    "facts": [],
    "world_variables": {},
}
MIN_CHARS = {
    "player": {"name": "P", "class": "mage", "stats": {"hp": 10, "mana": 5, "focus": 5}},
    "npcs": [],
}


@pytest.fixture
def client() -> TestClient:
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


def _signup_login(client: TestClient, email: str = "w@example.com") -> str:
    r = client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "username": "W",
            "password": "password123",
            "invite_code": "",
        },
    )
    assert r.status_code == 201, r.text
    r = client.post(
        "/api/auth/login",
        json={"email": email, "password": "password123"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_worlds_crud_flow(client: TestClient) -> None:
    token = _signup_login(client)
    h = {"Authorization": f"Bearer {token}"}

    r = client.get("/api/worlds/", headers=h)
    assert r.status_code == 200
    assert r.json() == []

    body = {
        "name": "My UGC",
        "world": MIN_WORLD,
        "characters": MIN_CHARS,
        "events": None,
    }
    r = client.post("/api/worlds/", headers=h, json=body)
    assert r.status_code == 201, r.text
    data = r.json()
    wid = data["id"]
    uuid.UUID(wid)
    assert data["name"] == "My UGC"
    assert data["world"]["id"] == "ugc_test"

    r = client.get("/api/worlds/", headers=h)
    assert r.status_code == 200
    lst = r.json()
    assert len(lst) == 1
    assert lst[0]["world_id"] == "ugc_test"
    assert lst[0].get("visibility") == "private"

    r = client.get(f"/api/worlds/{wid}", headers=h)
    assert r.status_code == 200
    assert r.json()["name"] == "My UGC"

    body["name"] = "Renamed"
    body["world"] = {**MIN_WORLD, "name": "Renamed world"}
    r = client.put(f"/api/worlds/{wid}", headers=h, json=body)
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed"

    r = client.delete(f"/api/worlds/{wid}", headers=h)
    assert r.status_code == 204

    r = client.get(f"/api/worlds/{wid}", headers=h)
    assert r.status_code == 404


def test_worlds_limit_and_isolation(client: TestClient) -> None:
    t_a = _signup_login(client, "a@example.com")
    t_b = _signup_login(client, "b@example.com")
    h_a = {"Authorization": f"Bearer {t_a}"}
    h_b = {"Authorization": f"Bearer {t_b}"}

    body = {
        "name": "W",
        "world": MIN_WORLD,
        "characters": MIN_CHARS,
    }
    for i in range(3):
        r = client.post(
            "/api/worlds/",
            headers=h_a,
            json={**body, "name": f"W{i}", "world": {**MIN_WORLD, "id": f"ugc_{i}"}},
        )
        assert r.status_code == 201, r.text

    r = client.post("/api/worlds/", headers=h_a, json=body)
    assert r.status_code == 409

    r = client.post("/api/worlds/", headers=h_b, json=body)
    assert r.status_code == 201

    r = client.get("/api/worlds/", headers=h_a)
    ids_a = {x["world_id"] for x in r.json()}
    assert ids_a == {"ugc_0", "ugc_1", "ugc_2"}

    first_id = r.json()[0]["id"]
    r = client.get(f"/api/worlds/{first_id}", headers=h_b)
    assert r.status_code == 404


def test_worlds_unauthenticated(client: TestClient) -> None:
    r = client.get("/api/worlds/")
    assert r.status_code == 401


def test_worlds_explore_public_only(client: TestClient) -> None:
    t_a = _signup_login(client, "pub_a@example.com")
    t_b = _signup_login(client, "pub_b@example.com")
    h_a = {"Authorization": f"Bearer {t_a}"}
    h_b = {"Authorization": f"Bearer {t_b}"}

    r = client.get("/api/worlds/explore", headers=h_b)
    assert r.status_code == 200
    assert r.json() == []

    client.post(
        "/api/worlds/",
        headers=h_a,
        json={
            "name": "비공개",
            "world": {**MIN_WORLD, "id": "priv_w"},
            "characters": MIN_CHARS,
            "visibility": "private",
        },
    )
    client.post(
        "/api/worlds/",
        headers=h_a,
        json={
            "name": "공개",
            "world": {**MIN_WORLD, "id": "pub_w"},
            "characters": MIN_CHARS,
            "visibility": "public",
        },
    )

    r = client.get("/api/worlds/explore", headers=h_b)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["name"] == "공개"
    assert data[0]["world_id"] == "pub_w"
    assert data[0]["owner_username"] == "W"
    assert data[0]["is_mine"] is False

    r = client.get("/api/worlds/explore", headers=h_a)
    assert r.json()[0]["is_mine"] is True


def test_worlds_explore_unauthenticated(client: TestClient) -> None:
    r = client.get("/api/worlds/explore")
    assert r.status_code == 401
