"""사용자 여정 스모크 — 가입 → 월드 생성 → 플레이 시작 → 턴 1회 (Epic I DoD).

실제 Anthropic 호출 없음 (`StubGameEngine`). CI 기본 게이트에 포함.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.tests.smoke.conftest import MIN_CHARS, MIN_WORLD


@pytest.mark.smoke
def test_signup_create_world_start_play_one_turn(smoke_api_client: TestClient) -> None:
    c = smoke_api_client

    assert (
        c.post(
            "/api/auth/signup",
            json={
                "email": "smoke@example.com",
                "username": "SmokeUser",
                "password": "password123",
                "invite_code": "",
            },
        ).status_code
        == 201
    )

    r_login = c.post(
        "/api/auth/login",
        json={"email": "smoke@example.com", "password": "password123"},
    )
    assert r_login.status_code == 200
    token = r_login.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    r_world = c.post(
        "/api/worlds/",
        headers=h,
        json={"name": "SmokeWorld", "world": MIN_WORLD, "characters": MIN_CHARS},
    )
    assert r_world.status_code == 201, r_world.text
    world_id = r_world.json()["id"]

    r_start = c.post(
        "/api/play/start",
        headers=h,
        json={
            "world_id": world_id,
            "player": {
                "name": "Smoke",
                "class": "tester",
                "stats": {"hp": 10, "mana": 5, "focus": 5},
            },
        },
    )
    assert r_start.status_code == 201, r_start.text
    session_id = r_start.json()["session_id"]

    r_turn = c.post(
        f"/api/play/{session_id}/turn",
        headers=h,
        json={"message": "스모크 테스트 턴"},
    )
    assert r_turn.status_code == 200, r_turn.text
    body = r_turn.json()
    assert body["response"] == "stub:스모크 테스트 턴"
    assert body["turn"] == 2
