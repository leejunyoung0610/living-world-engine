"""플레이 API — Stub GameEngine (LLM 없음)."""

from __future__ import annotations

from types import SimpleNamespace

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
from backend.src.engine.state import WorldState
from backend.src.main import create_app
from backend.src.services.play_session_db import delete_all_play_sessions
from backend.src.services.play_sessions import clear_all_sessions
from backend.src.utils.usage_tracker import UsageTracker

MIN_WORLD = {
    "id": "p_test",
    "name": "P",
    "description": "",
    "time": "t",
    "regions": [],
    "facts": [],
    "world_variables": {},
}
MIN_CHARS = {
    "npcs": [],
}
MIN_GENRES = ["fantasy"]
PLAYER_START = {
    "name": "P",
    "class": "c",
    "stats": {"hp": 10, "mana": 5, "focus": 5},
}


class StubGameEngine:
    """스냅샷 직렬화(`to_save_dict` 등)에 맞추기 위해 `WorldState` 사용."""

    def __init__(self) -> None:
        self.state = WorldState.load_from_dicts(MIN_WORLD, MIN_CHARS)
        self.conversation_history: list[dict[str, str]] = []
        self.event_manager = SimpleNamespace(triggered_events=[], cooldowns={})
        self.validator = SimpleNamespace(set_valid_characters=lambda *_: None)
        self.context_manager = SimpleNamespace(set_npc_names=lambda *_: None)
        self.memory = SimpleNamespace(
            set_npc_names=lambda *_: None,
            memories=[],
            _save=lambda: None,
        )
        self.usage_tracker = UsageTracker(llm_model="claude-sonnet-4-20250514")

    def initialize_from_dicts(self, *args: object, **kwargs: object) -> None:
        world_data = args[0] if args else MIN_WORLD
        chars_data = args[1] if len(args) > 1 else MIN_CHARS
        self.state = WorldState.load_from_dicts(
            world_data,  # type: ignore[arg-type]
            chars_data,  # type: ignore[arg-type]
        )
        self.conversation_history = []
        self.event_manager = SimpleNamespace(triggered_events=[], cooldowns={})
        self.usage_tracker = UsageTracker(llm_model="claude-sonnet-4-20250514")

    def process_turn(self, msg: str) -> dict:
        self.conversation_history.append({"role": "user", "content": msg})
        reply = f"stub:{msg}"
        self.conversation_history.append({"role": "assistant", "content": reply})
        self.state.turn = 2
        self.state.day = 1
        return {
            "turn": 2,
            "day": 1,
            "response": reply,
            "events_triggered": [{
                "event_id": "e1",
                "name": "테스트 이벤트",
                "description": "이벤트",
                "narrative_hint": "",
                "applied_effects": [
                    {"type": "resource_stat", "key": "focus", "change": 2, "before": 5, "after": 7},
                ],
            }],
        }

    def process_turn_stream(self, msg: str):
        self.conversation_history.append({"role": "user", "content": msg})
        reply = f"stub:{msg}"
        chunks = [reply[i : i + 2] for i in range(0, len(reply), 2)] or [""]
        for c in chunks:
            yield {"type": "delta", "text": c}
        self.conversation_history.append({"role": "assistant", "content": reply})
        self.state.turn = 2
        self.state.day = 1
        yield {
            "type": "done",
            "result": {
                "turn": 2,
                "day": 1,
                "response": reply,
                "events_triggered": [{
                    "event_id": "e1",
                    "name": "테스트 이벤트",
                    "description": "이벤트",
                    "narrative_hint": "",
                    "applied_effects": [
                        {"type": "resource_stat", "key": "focus", "change": 2, "before": 5, "after": 7},
                    ],
                }],
            },
        }


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
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


def _signup_token(client: TestClient, email: str = "p@example.com") -> str:
    assert client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "username": "P",
            "password": "password123",
            "invite_code": "",
        },
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


def test_play_start_and_turn(client: TestClient) -> None:
    token = _signup_token(client)
    wid = _create_world(client, token)
    h = {"Authorization": f"Bearer {token}"}

    r = client.post("/api/play/start", headers=h, json={"world_id": wid, "player": PLAYER_START})
    assert r.status_code == 201, r.text
    data = r.json()
    assert "session_id" in data
    assert data["world_name"] == "W"
    sid = data["session_id"]

    r = client.post(
        f"/api/play/{sid}/turn",
        headers=h,
        json={"message": "안녕"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["response"] == "stub:안녕"
    assert body["turn"] == 2
    assert len(body["events_triggered"]) >= 1
    eff = body["events_triggered"][0]["applied_effects"][0]
    assert eff["delta"] == 2
    assert eff["label_ko"] == "집중력"
    assert "response_segments" in body
    assert len(body["response_segments"]) >= 1


def test_play_relationships_endpoint(client: TestClient) -> None:
    token = _signup_token(client, "rel@example.com")
    h = {"Authorization": f"Bearer {token}"}
    chars = {
        "npcs": [
            {
                "id": "kim",
                "name": "김선배",
                "role": "선배",
                "relationship_stats": {"affection": 60, "trust": 40},
            }
        ]
    }
    r = client.post(
        "/api/worlds/",
        headers=h,
        json={"name": "RelW", "world": MIN_WORLD, "characters": chars, "genres": MIN_GENRES},
    )
    assert r.status_code == 201
    wid = r.json()["id"]

    r = client.post("/api/play/start", headers=h, json={"world_id": wid, "player": PLAYER_START})
    assert r.status_code == 201
    sid = r.json()["session_id"]

    r = client.get(f"/api/play/{sid}/relationships", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["npcs"]) == 1
    assert data["npcs"][0]["npc_name"] == "김선배"
    assert data["npcs"][0]["stats"] == {"affection": 60, "trust": 40}


def test_play_history_after_turn(client: TestClient) -> None:
    token = _signup_token(client)
    wid = _create_world(client, token)
    h = {"Authorization": f"Bearer {token}"}

    r = client.post("/api/play/start", headers=h, json={"world_id": wid, "player": PLAYER_START})
    sid = r.json()["session_id"]

    r = client.post(f"/api/play/{sid}/turn", headers=h, json={"message": "hi"})
    assert r.status_code == 200

    r = client.get(f"/api/play/{sid}/history", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["turn"] == 2
    assert data["world_name"] == "W"
    assert len(data["messages"]) == 2
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][1]["role"] == "assistant"


def test_play_start_not_owner(client: TestClient) -> None:
    t_a = _signup_token(client, "a@example.com")
    t_b = _signup_token(client, "b@example.com")
    wid = _create_world(client, t_a)

    r = client.post(
        "/api/play/start",
        headers={"Authorization": f"Bearer {t_b}"},
        json={"world_id": wid},
    )
    assert r.status_code == 404


def test_play_start_public_world_other_user(client: TestClient) -> None:
    t_a = _signup_token(client, "owner_pub@example.com")
    t_b = _signup_token(client, "player_pub@example.com")
    h_a = {"Authorization": f"Bearer {t_a}"}
    h_b = {"Authorization": f"Bearer {t_b}"}

    r = client.post(
        "/api/worlds/",
        headers=h_a,
        json={
            "name": "공개월드",
            "world": {**MIN_WORLD, "id": "open_ugc"},
            "characters": MIN_CHARS,
            "visibility": "public",
            "genres": MIN_GENRES,
        },
    )
    assert r.status_code == 201, r.text
    wid = r.json()["id"]

    r = client.post(
        "/api/play/start",
        headers=h_b,
        json={"world_id": wid, "player": PLAYER_START},
    )
    assert r.status_code == 201, r.text
    assert r.json()["world_name"] == "공개월드"


def test_play_new_game_requires_player(client: TestClient) -> None:
    token = _signup_token(client)
    wid = _create_world(client, token)
    h = {"Authorization": f"Bearer {token}"}
    r = client.post("/api/play/start", headers=h, json={"world_id": wid})
    assert r.status_code == 422
    assert "player" in (r.json().get("detail") or "").lower()


def test_play_world_brief(client: TestClient) -> None:
    token = _signup_token(client)
    wid = _create_world(client, token)
    h = {"Authorization": f"Bearer {token}"}
    r = client.get(f"/api/play/world/{wid}/brief", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("list_name") == "W"
    assert data.get("story_title") == "P"
    assert data.get("npcs") == []
    assert data.get("world_setting") == ""
    assert data.get("cover_image_url") == ""


def test_play_world_brief_includes_cover_and_npc_portraits(client: TestClient) -> None:
    token = _signup_token(client)
    h = {"Authorization": f"Bearer {token}"}
    cover = "https://cdn.example.test/play-cover.webp"
    portrait = "https://cdn.example.test/npc.webp"
    r = client.post(
        "/api/worlds/",
        headers=h,
        json={
            "name": "Vis",
            "world": {
                **MIN_WORLD,
                "id": "vis_slug",
                "description": "짧은 소개",
                "cover_image_url": cover,
            },
            "characters": {
                "npcs": [
                    {"id": "nid1", "name": "둘리", "role": "등장인물", "portrait_image_url": portrait},
                ],
            },
            "genres": MIN_GENRES,
        },
    )
    assert r.status_code == 201, r.text
    wid = r.json()["id"]
    b = client.get(f"/api/play/world/{wid}/brief", headers=h)
    assert b.status_code == 200, b.text
    bd = b.json()
    assert bd.get("cover_image_url") == cover
    npcs = bd.get("npcs") or []
    assert len(npcs) == 1
    assert npcs[0].get("name") == "둘리"
    assert npcs[0].get("portrait_url") == portrait


def test_play_world_brief_returns_world_setting(client: TestClient) -> None:
    token = _signup_token(client)
    h = {"Authorization": f"Bearer {token}"}
    r = client.post(
        "/api/worlds/",
        headers=h,
        json={
            "name": "WS",
            "world": {**MIN_WORLD, "id": "ws_test", "world_setting": "상세\n설명문"},
            "characters": MIN_CHARS,
            "genres": MIN_GENRES,
        },
    )
    assert r.status_code == 201, r.text
    wid = r.json()["id"]
    rb = client.get(f"/api/play/world/{wid}/brief", headers=h)
    assert rb.status_code == 200, rb.text
    assert "상세" in rb.json()["world_setting"]
    assert "설명문" in rb.json()["world_setting"]


def test_play_turn_wrong_session(client: TestClient) -> None:
    import uuid

    token = _signup_token(client)
    r = client.post(
        f"/api/play/{uuid.uuid4()}/turn",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "x"},
    )
    assert r.status_code == 404


def test_play_resume_same_world(client: TestClient) -> None:
    token = _signup_token(client)
    wid = _create_world(client, token)
    h = {"Authorization": f"Bearer {token}"}

    r1 = client.post(
        "/api/play/start", headers=h, json={"world_id": wid, "player": PLAYER_START}
    )
    assert r1.status_code == 201
    sid1 = r1.json()["session_id"]
    assert r1.json().get("resumed") is False

    r2 = client.post("/api/play/start", headers=h, json={"world_id": wid})
    assert r2.status_code == 200
    assert r2.json()["session_id"] == sid1
    assert r2.json().get("resumed") is True


def test_play_resume_from_db_after_memory_clear(client: TestClient) -> None:
    """인메모리 캐시만 비운 뒤에도 DB 스냅샷으로 동일 세션·대화가 복구되는지."""
    token = _signup_token(client)
    wid = _create_world(client, token)
    h = {"Authorization": f"Bearer {token}"}

    r1 = client.post(
        "/api/play/start", headers=h, json={"world_id": wid, "player": PLAYER_START}
    )
    sid1 = r1.json()["session_id"]
    client.post(f"/api/play/{sid1}/turn", headers=h, json={"message": "persist me"})

    clear_all_sessions()

    r2 = client.post("/api/play/start", headers=h, json={"world_id": wid})
    assert r2.status_code == 200
    assert r2.json()["session_id"] == sid1
    assert r2.json().get("resumed") is True

    rh = client.get(f"/api/play/{sid1}/history", headers=h)
    assert rh.status_code == 200
    contents = [m.get("content", "") for m in rh.json()["messages"]]
    assert any("persist me" in c for c in contents)


def test_play_force_new_different_session(client: TestClient) -> None:
    token = _signup_token(client)
    wid = _create_world(client, token)
    h = {"Authorization": f"Bearer {token}"}

    r1 = client.post(
        "/api/play/start", headers=h, json={"world_id": wid, "player": PLAYER_START}
    )
    sid1 = r1.json()["session_id"]

    r2 = client.post(
        "/api/play/start",
        headers=h,
        json={"world_id": wid, "force_new": True, "player": PLAYER_START},
    )
    assert r2.status_code == 201
    sid2 = r2.json()["session_id"]
    assert sid2 != sid1


def test_play_list_sessions(client: TestClient) -> None:
    token = _signup_token(client)
    wid = _create_world(client, token)
    h = {"Authorization": f"Bearer {token}"}

    r = client.get("/api/play/sessions", headers=h)
    assert r.status_code == 200
    assert r.json() == []

    client.post(
        "/api/play/start",
        headers=h,
        json={"world_id": wid, "player": PLAYER_START},
    )
    r = client.get("/api/play/sessions", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["world_name"] == "W"
    assert data[0]["is_world_owner"] is True
    assert "session_id" in data[0]


def test_play_turn_emergency_shutdown_platform_user_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = _signup_token(client, "emg@example.com")
    wid = _create_world(client, token)
    monkeypatch.setenv("EMERGENCY_SHUTDOWN", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-test-for-platform-path")
    h = {"Authorization": f"Bearer {token}"}
    sid = client.post(
        "/api/play/start", headers=h, json={"world_id": wid, "player": PLAYER_START}
    ).json()["session_id"]
    r = client.post(f"/api/play/{sid}/turn", headers=h, json={"message": "hi"})
    assert r.status_code == 503
    assert "긴급" in r.json()["detail"]


def test_play_turn_platform_quota_429(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENFORCE_PLATFORM_TURN_QUOTA", "true")
    monkeypatch.setenv("PLATFORM_DAILY_TURN_LIMIT", "2")

    token = _signup_token(client, "quota@example.com")
    wid = _create_world(client, token)
    h = {"Authorization": f"Bearer {token}"}
    sid = client.post(
        "/api/play/start", headers=h, json={"world_id": wid, "player": PLAYER_START}
    ).json()["session_id"]

    assert client.post(f"/api/play/{sid}/turn", headers=h, json={"message": "a"}).status_code == 200
    assert client.post(f"/api/play/{sid}/turn", headers=h, json={"message": "b"}).status_code == 200
    r = client.post(f"/api/play/{sid}/turn", headers=h, json={"message": "c"})
    assert r.status_code == 429
    assert "한도" in r.json()["detail"]


def test_play_delete_session(client: TestClient) -> None:
    token = _signup_token(client)
    wid = _create_world(client, token)
    h = {"Authorization": f"Bearer {token}"}

    sid = client.post(
        "/api/play/start", headers=h, json={"world_id": wid, "player": PLAYER_START}
    ).json()["session_id"]
    r = client.delete(f"/api/play/{sid}", headers=h)
    assert r.status_code == 204

    r = client.post(f"/api/play/{sid}/turn", headers=h, json={"message": "x"})
    assert r.status_code == 404
