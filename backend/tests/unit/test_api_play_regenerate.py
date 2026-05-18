"""플레이 API — 마지막 응답 재생성 스트림."""

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

from .test_api_play import MIN_CHARS, MIN_GENRES, MIN_WORLD, PLAYER_START, StubGameEngine


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("backend.src.api.routes.play.GameEngine", StubGameEngine)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-test-regenerate")

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


def _signup_token(client: TestClient, email: str = "regen@example.com") -> str:
    assert client.post(
        "/api/auth/signup",
        json={"email": email, "username": "R", "password": "password123", "invite_code": ""},
    ).status_code == 201
    r = client.post("/api/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200
    return r.json()["access_token"]


def _create_world(client: TestClient, token: str) -> str:
    r = client.post(
        "/api/worlds/",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "W", "world": MIN_WORLD, "characters": MIN_CHARS, "genres": MIN_GENRES},
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


def test_regenerate_stream_after_turn(client: TestClient) -> None:
    token = _signup_token(client)
    wid = _create_world(client, token)
    sid = _start_session(client, token, wid)
    h = {"Authorization": f"Bearer {token}"}

    r = client.post(
        f"/api/play/{sid}/turn/stream",
        headers=h,
        json={"message": "안녕"},
    )
    assert r.status_code == 200, r.text
    ev1 = _parse_sse(r.text)
    assert ev1[-1]["event"] == "done"
    assert ev1[-1]["data"]["response"] == "stub:안녕"

    r2 = client.post(
        f"/api/play/{sid}/turn/regenerate/stream",
        headers=h,
    )
    assert r2.status_code == 200, r2.text
    ev2 = _parse_sse(r2.text)
    assert ev2[-1]["event"] == "done"
    assert ev2[-1]["data"]["response"] == "stub:안녕"

    r3 = client.get(f"/api/play/{sid}/history", headers=h)
    assert r3.status_code == 200, r3.text
    msgs = r3.json()["messages"]
    assert len(msgs) == 2
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["content"] == "stub:안녕"


def test_regenerate_stream_with_edited_user_message(client: TestClient) -> None:
    token = _signup_token(client, "regen_edit@example.com")
    wid = _create_world(client, token)
    sid = _start_session(client, token, wid)
    h = {"Authorization": f"Bearer {token}"}

    r = client.post(
        f"/api/play/{sid}/turn/stream",
        headers=h,
        json={"message": "원문"},
    )
    assert r.status_code == 200, r.text
    ev1 = _parse_sse(r.text)
    assert ev1[-1]["event"] == "done"
    assert ev1[-1]["data"]["response"] == "stub:원문"

    r2 = client.post(
        f"/api/play/{sid}/turn/regenerate/stream",
        headers={**h, "Content-Type": "application/json"},
        json={"message": "고친말"},
    )
    assert r2.status_code == 200, r2.text
    ev2 = _parse_sse(r2.text)
    assert ev2[-1]["event"] == "done"
    assert ev2[-1]["data"]["response"] == "stub:고친말"

    r3 = client.get(f"/api/play/{sid}/history", headers=h)
    assert r3.status_code == 200, r3.text
    msgs = r3.json()["messages"]
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "고친말"
    assert msgs[1]["content"] == "stub:고친말"


def test_regenerate_409_without_checkpoint(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.src.api.routes import play as play_mod

    orig = play_mod._ensure_bundle

    def _wrap_db_bundle(db, session_id, user_id):  # type: ignore[no-untyped-def]
        b = orig(db, session_id, user_id)
        if b is not None:
            b.regenerate_checkpoint = None
        return b

    monkeypatch.setattr(play_mod, "_ensure_bundle", _wrap_db_bundle)

    token = _signup_token(client, "regen2@example.com")
    wid = _create_world(client, token)
    sid = _start_session(client, token, wid)

    r = client.post(
        f"/api/play/{sid}/turn/regenerate/stream",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 409


def test_regenerate_requires_auth(client: TestClient) -> None:
    token = _signup_token(client, "regen3@example.com")
    wid = _create_world(client, token)
    sid = _start_session(client, token, wid)
    r = client.post(f"/api/play/{sid}/turn/regenerate/stream")
    assert r.status_code == 401
