"""플레이 API — SSE 스트리밍 (Stub GameEngine)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.src.db.base import Base
from backend.src.db.models import (  # noqa: F401
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

from .test_api_play import MIN_CHARS, MIN_WORLD, PLAYER_START, StubGameEngine


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("backend.src.api.routes.play.GameEngine", StubGameEngine)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-test-stream")

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


def _signup_token(client: TestClient, email: str = "stream@example.com") -> str:
    assert client.post(
        "/api/auth/signup",
        json={"email": email, "username": "S", "password": "password123", "invite_code": ""},
    ).status_code == 201
    r = client.post("/api/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200
    return r.json()["access_token"]


def _create_world(client: TestClient, token: str) -> str:
    r = client.post(
        "/api/worlds/",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "W", "world": MIN_WORLD, "characters": MIN_CHARS},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _start_session(client: TestClient, token: str, world_id: str) -> str:
    r = client.post(
        "/api/play/start",
        headers={"Authorization": f"Bearer {token}"},
        json={"world_id": world_id, "player": PLAYER_START},
    )
    assert r.status_code == 201, r.text
    return r.json()["session_id"]


def _parse_sse(text: str) -> list[dict]:
    """Raw SSE 본문을 (event_type, data) 리스트로 파싱."""
    events: list[dict] = []
    for chunk in text.split("\n\n"):
        chunk = chunk.strip("\n")
        if not chunk.strip():
            continue
        ev_type = "message"
        data_lines: list[str] = []
        for line in chunk.split("\n"):
            if line.startswith("event:"):
                ev_type = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].strip())
        if not data_lines:
            continue
        events.append({"event": ev_type, "data": json.loads("\n".join(data_lines))})
    return events


def test_stream_emits_delta_then_done(client: TestClient) -> None:
    token = _signup_token(client)
    wid = _create_world(client, token)
    sid = _start_session(client, token, wid)

    r = client.post(
        f"/api/play/{sid}/turn/stream",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "안녕"},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/event-stream")
    assert r.headers.get("cache-control") == "no-cache"
    assert r.headers.get("x-accel-buffering") == "no"

    events = _parse_sse(r.text)
    assert len(events) >= 2
    assert events[0]["event"] == "delta"
    assert events[-1]["event"] == "done"

    deltas = [e["data"]["text"] for e in events if e["event"] == "delta"]
    assert "".join(deltas) == "stub:안녕"

    done = events[-1]["data"]
    assert done["turn"] == 2
    assert done["day"] == 1
    assert done["response"] == "stub:안녕"
    assert done["response_segments"]
    assert done["events_triggered"][0]["event_id"] == "e1"


def test_stream_requires_auth(client: TestClient) -> None:
    token = _signup_token(client)
    wid = _create_world(client, token)
    sid = _start_session(client, token, wid)

    r = client.post(f"/api/play/{sid}/turn/stream", json={"message": "안녕"})
    assert r.status_code == 401


def test_stream_unknown_session_returns_404(client: TestClient) -> None:
    token = _signup_token(client)
    r = client.post(
        "/api/play/00000000-0000-0000-0000-000000000000/turn/stream",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "안녕"},
    )
    assert r.status_code == 404


def test_stream_other_user_cannot_access(client: TestClient) -> None:
    t_a = _signup_token(client, "a_stream@example.com")
    t_b = _signup_token(client, "b_stream@example.com")
    wid = _create_world(client, t_a)
    sid = _start_session(client, t_a, wid)

    r = client.post(
        f"/api/play/{sid}/turn/stream",
        headers={"Authorization": f"Bearer {t_b}"},
        json={"message": "안녕"},
    )
    assert r.status_code == 404
