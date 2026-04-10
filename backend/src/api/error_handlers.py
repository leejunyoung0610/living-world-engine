"""공통 HTTP 예외 응답 — 검증 오류 메시지·미처리 예외 로깅."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI, *, debug: bool) -> None:
    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.debug("RequestValidationError: %s", exc.errors())
        body: dict[str, Any] = {
            "detail": "요청 형식이 올바르지 않습니다.",
            "errors": exc.errors(),
        }
        if debug and exc.body is not None:
            body["body"] = exc.body
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=body)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception")
        msg = "서버 내부 오류가 발생했습니다."
        if debug:
            msg = f"{msg} ({type(exc).__name__}: {exc})"
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": msg},
        )
