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
    "npcs": [],
}
MIN_GENRES = ["fantasy"]


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
        "genres": MIN_GENRES,
    }
    r = client.post("/api/worlds/", headers=h, json=body)
    assert r.status_code == 201, r.text
    data = r.json()
    wid = data["id"]
    uuid.UUID(wid)
    assert data["name"] == "My UGC"
    assert data["world"]["id"] == "ugc_test"
    assert data["characters"] == {"npcs": []}
    assert data.get("genres") == ["fantasy"]

    r = client.get("/api/worlds/", headers=h)
    assert r.status_code == 200
    lst = r.json()
    assert len(lst) == 1
    assert lst[0]["world_id"] == "ugc_test"
    assert lst[0].get("visibility") == "private"
    assert lst[0].get("genres") == ["fantasy"]

    r = client.get(f"/api/worlds/{wid}", headers=h)
    assert r.status_code == 200
    assert r.json()["name"] == "My UGC"

    body["name"] = "Renamed"
    body["world"] = {**MIN_WORLD, "name": "Renamed world"}
    body["genres"] = ["fantasy", "romance"]
    r = client.put(f"/api/worlds/{wid}", headers=h, json=body)
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed"
    assert r.json().get("genres") == ["fantasy", "romance"]

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
        "genres": MIN_GENRES,
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
    assert r.json() == {"items": [], "total": 0, "limit": 20, "offset": 0}

    client.post(
        "/api/worlds/",
        headers=h_a,
        json={
            "name": "비공개",
            "world": {**MIN_WORLD, "id": "priv_w"},
            "characters": MIN_CHARS,
            "visibility": "private",
            "genres": MIN_GENRES,
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
            "genres": MIN_GENRES,
        },
    )

    r = client.get("/api/worlds/explore", headers=h_b)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "공개"
    assert data["items"][0]["world_id"] == "pub_w"
    assert data["items"][0]["owner_username"] == "W"
    assert data["items"][0]["is_mine"] is False

    r = client.get("/api/worlds/explore", headers=h_a)
    assert r.json()["items"][0]["is_mine"] is True


def test_worlds_explore_pagination(client: TestClient) -> None:
    token = _signup_login(client, "pag@example.com")
    h = {"Authorization": f"Bearer {token}"}
    body = {
        "name": "W",
        "world": MIN_WORLD,
        "characters": MIN_CHARS,
        "visibility": "public",
        "genres": MIN_GENRES,
    }
    # 계정당 월드 상한(기본 3)에 맞춤
    for i in range(3):
        r = client.post(
            "/api/worlds/",
            headers=h,
            json={
                **body,
                "name": f"P{i}",
                "world": {**MIN_WORLD, "id": f"pub_pag_{i}"},
            },
        )
        assert r.status_code == 201, r.text

    r = client.get("/api/worlds/explore?limit=2&offset=0", headers=h)
    assert r.status_code == 200
    p1 = r.json()
    assert p1["total"] == 3
    assert p1["limit"] == 2
    assert p1["offset"] == 0
    assert len(p1["items"]) == 2

    r = client.get("/api/worlds/explore?limit=2&offset=2", headers=h)
    p2 = r.json()
    assert p2["total"] == 3
    assert len(p2["items"]) == 1

    r = client.get("/api/worlds/explore?limit=100&offset=0", headers=h)
    assert r.json()["total"] == 3
    assert len(r.json()["items"]) == 3


def test_worlds_explore_unauthenticated(client: TestClient) -> None:
    r = client.get("/api/worlds/explore")
    assert r.status_code == 401


def test_genre_catalog_public(client: TestClient) -> None:
    r = client.get("/api/worlds/meta/genres")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list) and len(data) >= 5
    assert {"slug", "label"} == set(data[0].keys())


def test_worlds_explore_genre_and_popular(client: TestClient) -> None:
    token = _signup_login(client, "sort@example.com")
    h = {"Authorization": f"Bearer {token}"}
    for i, g in enumerate([["romance"], ["fantasy", "romance"], ["sf"]]):
        client.post(
            "/api/worlds/",
            headers=h,
            json={
                "name": f"G{i}",
                "world": {**MIN_WORLD, "id": f"sort_{i}"},
                "characters": MIN_CHARS,
                "visibility": "public",
                "genres": g,
            },
        )
    r = client.get("/api/worlds/explore?genre=romance", headers=h)
    assert r.status_code == 200
    names = [x["name"] for x in r.json()["items"]]
    assert "G0" in names and "G1" in names and "G2" not in names

    r_all = client.get("/api/worlds/explore?sort=latest", headers=h)
    wid = next(x["id"] for x in r_all.json()["items"] if x["name"] == "G0")
    assert (
        client.post(
            "/api/play/start",
            headers=h,
            json={"world_id": wid, "player": {"name": "x", "class": "c", "stats": {"hp": 1}}},
        ).status_code
        == 201
    )
    r_pop = client.get("/api/worlds/explore?sort=popular", headers=h)
    assert r_pop.json()["items"][0]["play_start_count"] >= 1
