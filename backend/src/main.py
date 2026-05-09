"""FastAPI 앱 — UGC MVP Day 0 + 인증 수직 슬라이스."""

from __future__ import annotations

import logging

import sentry_sdk
from fastapi import Depends, FastAPI, HTTPException
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.requests import Request

from .api.error_handlers import register_exception_handlers
from .api.limiter import limiter
from .api.request_context_middleware import RequestContextMiddleware
from .api.routes import auth as auth_routes
from .api.routes import kakao as kakao_routes
from .api.routes import play as play_routes
from .api.routes import worlds as worlds_routes
from .api.security import SecurityHeadersMiddleware, validate_cors_origins_for_production
from .db.session import get_db
from .utils.config import Settings, get_settings
from .utils.logging_setup import configure_logging

logger = logging.getLogger(__name__)


def _init_sentry(settings: Settings) -> None:
    dsn = (settings.sentry_dsn or "").strip()
    if not dsn:
        return
    env = settings.sentry_environment
    if not env:
        env = "development" if settings.debug else "production"
    sentry_sdk.init(
        dsn=dsn,
        environment=env,
        integrations=[
            StarletteIntegration(),
            FastApiIntegration(),
        ],
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
    )


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(structured=settings.structured_logging, debug=settings.debug)
    _init_sentry(settings)
    limiter.enabled = settings.rate_limiting_enabled

    app = FastAPI(
        title="Living World Engine API",
        version="0.5.0",
        description="UGC MVP: auth, worlds (private/public), explore, browser play (DB → GameEngine, session resume)",
    )
    app.state.limiter = limiter

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    validate_cors_origins_for_production(debug=settings.debug, origins=origins)

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware, settings=settings)
    app.include_router(auth_routes.router, prefix="/api/auth", tags=["auth"])
    app.include_router(kakao_routes.router, prefix="/api/auth", tags=["auth"])
    app.include_router(worlds_routes.router, prefix="/api/worlds", tags=["worlds"])
    app.include_router(play_routes.router, prefix="/api/play", tags=["play"])

    register_exception_handlers(app, debug=settings.debug)

    @app.exception_handler(RateLimitExceeded)
    def rate_limit_handler(_request: Request, exc: RateLimitExceeded) -> JSONResponse:
        _ = exc
        return JSONResponse(
            status_code=429,
            content={"detail": "요청이 너무 잦습니다. 잠시 후 다시 시도하세요."},
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        sentry_sdk.capture_exception(exc)
        rid = getattr(request.state, "request_id", None)
        logger.exception("SQLAlchemy error", extra={"request_id": rid} if rid else {})
        msg = (
            "데이터베이스 오류입니다. 프로젝트 루트에서 "
            "`poetry run python -m alembic upgrade head` 를 실행한 뒤 다시 시도하세요."
        )
        if settings.debug:
            orig = getattr(exc, "orig", None)
            if orig is not None:
                msg = f"{msg} (원인: {orig})"
        return JSONResponse(status_code=500, content={"detail": msg})

    @app.get("/health")
    def health(db: Session = Depends(get_db)) -> dict[str, str]:
        try:
            db.execute(text("SELECT 1"))
        except Exception:
            logger.exception("health database check failed")
            raise HTTPException(
                status_code=503,
                detail="데이터베이스에 연결할 수 없습니다.",
            ) from None
        return {"status": "ok", "database": "ok"}

    return app


app = create_app()
