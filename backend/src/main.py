"""FastAPI 앱 — UGC MVP Day 0 + 인증 수직 슬라이스."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request

from .api.routes import auth as auth_routes
from .api.routes import worlds as worlds_routes
from .utils.config import get_settings

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Living World Engine API",
        version="0.3.0",
        description="UGC MVP: auth, worlds CRUD, (추후) play",
    )
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_routes.router, prefix="/api/auth", tags=["auth"])
    app.include_router(worlds_routes.router, prefix="/api/worlds", tags=["worlds"])

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(_request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.exception("SQLAlchemy error")
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
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
