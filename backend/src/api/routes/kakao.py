"""카카오 OAuth 2.0 — Authorization Code 플로우.

흐름:
    1) 프론트가 ``GET /api/auth/kakao/authorize`` 로 이동 → 302 카카오 로그인 페이지.
    2) 사용자가 동의 → 카카오가 ``KAKAO_REDIRECT_URI`` 로 ``code`` 를 들고 리다이렉트.
    3) ``GET /api/auth/kakao/callback?code=...`` 가 토큰을 교환·프로필을 받아 유저 upsert,
       JWT를 ``KAKAO_POST_LOGIN_REDIRECT#access_token=...`` 형태로 프론트에 전달.

State는 stateless HMAC 토큰 (JWT 비밀로 서명) — 별도 세션 저장소 없이 CSRF 방지.
"""

from __future__ import annotations

import json
import logging
import secrets
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db.models import User
from ...db.session import get_db
from ...utils.config import Settings, get_settings
from .auth import issue_access_token

logger = logging.getLogger(__name__)
router = APIRouter()

KAKAO_AUTHORIZE_URL = "https://kauth.kakao.com/oauth/authorize"
KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_USER_URL = "https://kapi.kakao.com/v2/user/me"

# state JWT — 짧게 (5분), 다른 토큰과 구분되도록 ``aud`` 고정.
_STATE_AUDIENCE = "kakao-oauth-state"
_STATE_TTL_SECONDS = 5 * 60


def _require_enabled(settings: Settings) -> None:
    if not settings.kakao_login_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kakao login is disabled",
        )
    if not settings.kakao_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Kakao login is not configured",
        )


def _resolve_redirect_uri(settings: Settings, request: Request) -> str:
    """``KAKAO_REDIRECT_URI`` 가 비어있으면 요청 호스트에서 자동 도출.

    카카오 콘솔에 등록된 URI 중 *현재 요청과 동일한 호스트* 가 자동 선택되므로,
    동일 빌드를 ``localhost:8080``, ``172.30.x.y:8080``, 운영 도메인에 모두 사용 가능.
    """
    if settings.kakao_redirect_uri:
        return settings.kakao_redirect_uri
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/auth/kakao/callback"


def _sign_state(settings: Settings) -> str:
    payload = {
        "aud": _STATE_AUDIENCE,
        "nonce": secrets.token_urlsafe(16),
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(seconds=_STATE_TTL_SECONDS),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _verify_state(settings: Settings, raw: str) -> None:
    try:
        jwt.decode(
            raw,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience=_STATE_AUDIENCE,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state",
        ) from exc


def _http_post_form(url: str, fields: dict[str, str], *, timeout: float = 5.0) -> dict[str, Any]:
    body = urllib.parse.urlencode(fields).encode("utf-8")
    req = urllib.request.Request(  # noqa: S310 — 카카오 고정 URL
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace") if exc.fp is not None else str(exc)
        logger.warning("kakao token endpoint error: %s %s", exc.code, detail)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Kakao token exchange failed",
        ) from exc
    except URLError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Kakao network error",
        ) from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Kakao returned malformed JSON",
        ) from exc


def _http_get_json(url: str, bearer: str, *, timeout: float = 5.0) -> dict[str, Any]:
    req = urllib.request.Request(  # noqa: S310 — 카카오 고정 URL
        url,
        method="GET",
        headers={"Authorization": f"Bearer {bearer}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read()
    except HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Kakao userinfo failed",
        ) from exc
    except URLError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Kakao network error",
        ) from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Kakao returned malformed JSON",
        ) from exc


def _post_login_redirect(settings: Settings, request: Request) -> str:
    if settings.kakao_post_login_redirect:
        return settings.kakao_post_login_redirect.rstrip("/")
    base = str(request.base_url).rstrip("/")
    return f"{base}/oauth/callback"


def _redirect_with_error(settings: Settings, request: Request, code: str) -> RedirectResponse:
    target = _post_login_redirect(settings, request)
    return RedirectResponse(url=f"{target}#error={urllib.parse.quote(code)}", status_code=302)


def _stable_email_for_kakao(profile: dict[str, Any]) -> str:
    """카카오에서 email 동의를 받지 못한 경우 합성 식별자(@kakao.local) 발급."""
    account = profile.get("kakao_account") or {}
    raw_email = account.get("email")
    verified = account.get("is_email_valid") and account.get("is_email_verified")
    if isinstance(raw_email, str) and raw_email and verified:
        return raw_email.lower()
    kakao_id = profile.get("id")
    return f"kakao_{kakao_id}@kakao.local"


def _username_from_kakao(profile: dict[str, Any]) -> str:
    account = profile.get("kakao_account") or {}
    profile_block = account.get("profile") or {}
    nickname = profile_block.get("nickname")
    if isinstance(nickname, str) and nickname.strip():
        # 50자 컬럼 — 다바이트 nickname은 굳이 자르지 않음 (DB가 잘리는 게 더 안전)
        return nickname.strip()[:50]
    kakao_id = profile.get("id")
    return f"kakao_{kakao_id}"


@router.get("/kakao/authorize")
def kakao_authorize(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    """프론트에서 호출 → 카카오 인가 페이지로 302."""
    _require_enabled(settings)
    state = _sign_state(settings)
    params = {
        "response_type": "code",
        "client_id": settings.kakao_client_id,
        "redirect_uri": _resolve_redirect_uri(settings, request),
        "state": state,
        # 기본 동의항목만 사용. email은 콘솔에서 「선택」으로 활성화돼야 함.
        "scope": "account_email,profile_nickname",
    }
    return RedirectResponse(
        url=f"{KAKAO_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}",
        status_code=302,
    )


@router.get("/kakao/callback")
def kakao_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """카카오가 호출. 토큰 교환 → 유저 upsert → 프론트로 access_token 전달."""
    _require_enabled(settings)
    if error:
        return _redirect_with_error(settings, request, error)
    if not code or not state:
        return _redirect_with_error(settings, request, "missing_code")
    _verify_state(settings, state)

    token_fields = {
        "grant_type": "authorization_code",
        "client_id": settings.kakao_client_id,
        "redirect_uri": _resolve_redirect_uri(settings, request),
        "code": code,
    }
    if settings.kakao_client_secret:
        token_fields["client_secret"] = settings.kakao_client_secret

    token_resp = _http_post_form(KAKAO_TOKEN_URL, token_fields)
    access_token = token_resp.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        return _redirect_with_error(settings, request, "token_exchange_failed")

    profile = _http_get_json(KAKAO_USER_URL, access_token)
    kakao_id = profile.get("id")
    if kakao_id is None:
        return _redirect_with_error(settings, request, "no_kakao_id")
    kakao_sub = str(kakao_id)

    user = db.scalars(select(User).where(User.kakao_sub == kakao_sub)).first()
    if user is None:
        # email 일치하면 기존 로컬 계정과 자동 연결.
        email = _stable_email_for_kakao(profile)
        user = db.scalars(select(User).where(User.email == email)).first()
        if user is not None:
            user.kakao_sub = kakao_sub
            if user.auth_provider == "local":
                # 로컬 계정과 연결되더라도 첫 가입 경로는 보존 — auth_provider 는 유지.
                pass
        else:
            user = User(
                email=email,
                username=_username_from_kakao(profile),
                password_hash=None,
                auth_provider="kakao",
                kakao_sub=kakao_sub,
            )
            db.add(user)
    db.commit()

    jwt_token = issue_access_token(user.email)
    target = _post_login_redirect(settings, request)
    fragment = urllib.parse.urlencode(
        {"access_token": jwt_token, "token_type": "bearer", "provider": "kakao"}
    )
    return RedirectResponse(url=f"{target}#{fragment}", status_code=302)
