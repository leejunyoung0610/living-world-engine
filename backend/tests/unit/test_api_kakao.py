"""카카오 OAuth 라우트 — `urlopen` 모킹으로 토큰·프로필 교환 검증."""

from __future__ import annotations

import io
import json
import urllib.parse
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.src.api.routes import kakao as kakao_routes
from backend.src.db.base import Base
from backend.src.db.models import User
from backend.src.db.session import get_db
from backend.src.main import create_app
from backend.src.utils.config import get_settings


@pytest.fixture(autouse=True)
def _isolate_kakao_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """`.env` 가 KAKAO_* 를 채워 두면 테스트 간 격리가 깨진다.
    pydantic-settings 는 ``env_file`` 도 읽으므로 ``delenv`` 만으로는 불충분 →
    명시적 빈 값/false 로 덮어쓴다. 각 테스트는 ``kakao_env`` 로 필요한 키만 재설정.
    """
    monkeypatch.setenv("KAKAO_LOGIN_ENABLED", "false")
    monkeypatch.setenv("KAKAO_CLIENT_ID", "")
    monkeypatch.setenv("KAKAO_CLIENT_SECRET", "")
    monkeypatch.setenv("KAKAO_REDIRECT_URI", "")
    monkeypatch.setenv("KAKAO_POST_LOGIN_REDIRECT", "")


@pytest.fixture
def kakao_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KAKAO_LOGIN_ENABLED", "true")
    monkeypatch.setenv("KAKAO_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("KAKAO_REDIRECT_URI", "http://testserver/api/auth/kakao/callback")
    monkeypatch.setenv("KAKAO_POST_LOGIN_REDIRECT", "http://testserver/oauth/callback")


@pytest.fixture
def client_factory():
    def _make() -> tuple[TestClient, sessionmaker]:
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
        return TestClient(app), TestSessionLocal

    return _make


class _FakeResp:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._buf = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def __enter__(self) -> "_FakeResp":
        return self

    def __exit__(self, *_: Any) -> None:
        self._buf.close()

    def read(self) -> bytes:
        return self._buf.getvalue()


def _patch_kakao_http(
    monkeypatch: pytest.MonkeyPatch,
    *,
    token: dict[str, Any],
    profile: dict[str, Any],
    captured_token_body: dict[str, str] | None = None,
) -> None:
    def fake_urlopen(req, timeout: float = 5.0):  # noqa: ARG001
        url = req.full_url
        if url.startswith("https://kauth.kakao.com/oauth/token"):
            if captured_token_body is not None:
                raw = req.data.decode("utf-8") if req.data else ""
                for k, v in urllib.parse.parse_qsl(raw):
                    captured_token_body[k] = v
            return _FakeResp(token)
        if url.startswith("https://kapi.kakao.com/v2/user/me"):
            return _FakeResp(profile)
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(kakao_routes.urllib.request, "urlopen", fake_urlopen)


def test_kakao_authorize_redirects_to_kakao(kakao_env, client_factory) -> None:
    client, _ = client_factory()
    try:
        r = client.get("/api/auth/kakao/authorize", follow_redirects=False)
        assert r.status_code == 302
        loc = r.headers["location"]
        assert loc.startswith("https://kauth.kakao.com/oauth/authorize?")
        qs = dict(urllib.parse.parse_qsl(loc.split("?", 1)[1]))
        assert qs["client_id"] == "test-client-id"
        assert qs["redirect_uri"] == "http://testserver/api/auth/kakao/callback"
        assert qs["response_type"] == "code"
        assert qs["state"]
    finally:
        client.app.dependency_overrides.clear()


def test_kakao_authorize_404_when_disabled(client_factory) -> None:
    # 환경 미설정 → 404
    client, _ = client_factory()
    try:
        r = client.get("/api/auth/kakao/authorize", follow_redirects=False)
        assert r.status_code == 404
    finally:
        client.app.dependency_overrides.clear()


def test_kakao_callback_creates_new_user(
    kakao_env, client_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, str] = {}
    _patch_kakao_http(
        monkeypatch,
        token={"access_token": "kk-access", "token_type": "bearer"},
        profile={
            "id": 999111,
            "kakao_account": {
                "is_email_valid": True,
                "is_email_verified": True,
                "email": "Kakao.User@Example.com",
                "profile": {"nickname": "카카오닉"},
            },
        },
        captured_token_body=captured,
    )

    client, SessionLocal = client_factory()
    try:
        # state 발급
        r = client.get("/api/auth/kakao/authorize", follow_redirects=False)
        state = dict(urllib.parse.parse_qsl(r.headers["location"].split("?", 1)[1]))["state"]

        r = client.get(
            "/api/auth/kakao/callback",
            params={"code": "abc", "state": state},
            follow_redirects=False,
        )
        assert r.status_code == 302
        loc = r.headers["location"]
        assert loc.startswith("http://testserver/oauth/callback#")
        frag = dict(urllib.parse.parse_qsl(loc.split("#", 1)[1]))
        assert frag["provider"] == "kakao"
        token = frag["access_token"]

        settings = get_settings()
        decoded = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert decoded["sub"] == "kakao.user@example.com"

        # 토큰 교환 시 client_secret 미설정 → 본문에 포함되지 않아야 함.
        assert "client_secret" not in captured
        assert captured.get("grant_type") == "authorization_code"
        assert captured.get("code") == "abc"

        db = SessionLocal()
        u = db.scalars(select(User).where(User.kakao_sub == "999111")).one()
        assert u.auth_provider == "kakao"
        assert u.password_hash is None
        assert u.username == "카카오닉"
        db.close()
    finally:
        client.app.dependency_overrides.clear()


def test_kakao_callback_links_existing_local_user(
    kakao_env, client_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_kakao_http(
        monkeypatch,
        token={"access_token": "kk-access"},
        profile={
            "id": 555,
            "kakao_account": {
                "is_email_valid": True,
                "is_email_verified": True,
                "email": "linkme@example.com",
                "profile": {"nickname": "Link"},
            },
        },
    )

    client, SessionLocal = client_factory()
    try:
        # 로컬로 먼저 가입
        r = client.post(
            "/api/auth/signup",
            json={
                "email": "linkme@example.com",
                "username": "Local",
                "password": "password123",
                "invite_code": "",
            },
        )
        assert r.status_code == 201

        r = client.get("/api/auth/kakao/authorize", follow_redirects=False)
        state = dict(urllib.parse.parse_qsl(r.headers["location"].split("?", 1)[1]))["state"]

        r = client.get(
            "/api/auth/kakao/callback",
            params={"code": "abc", "state": state},
            follow_redirects=False,
        )
        assert r.status_code == 302

        db = SessionLocal()
        u = db.scalars(select(User).where(User.email == "linkme@example.com")).one()
        assert u.kakao_sub == "555"
        # 로컬 가입 경로는 보존
        assert u.auth_provider == "local"
        assert u.password_hash is not None
        db.close()
    finally:
        client.app.dependency_overrides.clear()


def test_kakao_callback_synthetic_email_when_no_consent(
    kakao_env, client_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_kakao_http(
        monkeypatch,
        token={"access_token": "kk-access"},
        profile={
            "id": 7777,
            "kakao_account": {
                # 동의 거부 → email 없음/미검증
                "is_email_valid": False,
                "is_email_verified": False,
                "profile": {"nickname": "  "},
            },
        },
    )

    client, SessionLocal = client_factory()
    try:
        r = client.get("/api/auth/kakao/authorize", follow_redirects=False)
        state = dict(urllib.parse.parse_qsl(r.headers["location"].split("?", 1)[1]))["state"]

        r = client.get(
            "/api/auth/kakao/callback",
            params={"code": "abc", "state": state},
            follow_redirects=False,
        )
        assert r.status_code == 302

        db = SessionLocal()
        u = db.scalars(select(User).where(User.kakao_sub == "7777")).one()
        assert u.email == "kakao_7777@kakao.local"
        assert u.username == "kakao_7777"
        db.close()
    finally:
        client.app.dependency_overrides.clear()


def test_kakao_callback_rejects_invalid_state(kakao_env, client_factory) -> None:
    client, _ = client_factory()
    try:
        r = client.get(
            "/api/auth/kakao/callback",
            params={"code": "abc", "state": "not-a-real-state"},
            follow_redirects=False,
        )
        assert r.status_code == 400
    finally:
        client.app.dependency_overrides.clear()


def test_kakao_callback_propagates_provider_error(kakao_env, client_factory) -> None:
    client, _ = client_factory()
    try:
        r = client.get(
            "/api/auth/kakao/callback",
            params={"error": "access_denied"},
            follow_redirects=False,
        )
        assert r.status_code == 302
        assert "error=access_denied" in r.headers["location"]
    finally:
        client.app.dependency_overrides.clear()


def test_login_blocks_password_for_kakao_only_user(
    kakao_env, client_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_kakao_http(
        monkeypatch,
        token={"access_token": "kk-access"},
        profile={
            "id": 12345,
            "kakao_account": {
                "is_email_valid": True,
                "is_email_verified": True,
                "email": "kakao-only@example.com",
                "profile": {"nickname": "K"},
            },
        },
    )

    client, _ = client_factory()
    try:
        r = client.get("/api/auth/kakao/authorize", follow_redirects=False)
        state = dict(urllib.parse.parse_qsl(r.headers["location"].split("?", 1)[1]))["state"]
        r = client.get(
            "/api/auth/kakao/callback",
            params={"code": "abc", "state": state},
            follow_redirects=False,
        )
        assert r.status_code == 302

        # 비밀번호 로그인은 막혀야 함
        r = client.post(
            "/api/auth/login",
            json={"email": "kakao-only@example.com", "password": "anything12345"},
        )
        assert r.status_code == 401
    finally:
        client.app.dependency_overrides.clear()
