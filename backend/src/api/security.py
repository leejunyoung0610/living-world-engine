"""보안 헤더·CORS 검증 (Epic F)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """최소 보안 헤더 — API JSON 위주, iframe 임베드 비권장."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return resp


def validate_cors_origins_for_production(*, debug: bool, origins: list[str]) -> None:
    """`allow_credentials=True` 일 때 `*` 오리진 금지 (FastAPI CORSMiddleware 규약)."""
    if debug:
        return
    for o in origins:
        if o.strip() == "*":
            raise RuntimeError(
                "CORS_ORIGINS 에 `*` 는 사용할 수 없습니다 (자격 증명 쿠키/JWT 브라우저 요청). "
                "프로덕션에서는 https:// 도메인을 명시하세요."
            )
