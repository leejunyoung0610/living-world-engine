"""FastAPI 앱 — UGC MVP Day 0 + 인증 수직 슬라이스."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import auth as auth_routes
from .api.routes import worlds as worlds_routes
from .utils.config import get_settings


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

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
