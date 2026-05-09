"""요청 컨텍스트 — request_id, Sentry 태그, 액세스 로그(Epic H)."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

import sentry_sdk
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ..utils.config import Settings

ACCESS_LOGGER = logging.getLogger("living_world.access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        self._structured = settings.structured_logging

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        sentry_sdk.get_isolation_scope().set_tag("request_id", request_id)

        start = time.perf_counter()
        response: Response | None = None
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except BaseException:
            status_code = 500
            raise
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            self._emit_access(request, request_id, status_code, duration_ms)
            if response is not None:
                response.headers["X-Request-Id"] = request_id

    def _emit_access(
        self,
        request: Request,
        request_id: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        if self._structured:
            ACCESS_LOGGER.info(
                "request",
                extra={
                    "request_id": request_id,
                    "http_method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                },
            )
        else:
            ACCESS_LOGGER.info(
                "%s %s %s %sms request_id=%s",
                request.method,
                request.url.path,
                status_code,
                duration_ms,
                request_id,
            )
