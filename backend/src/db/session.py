"""엔진·세션 팩토리·FastAPI get_db."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..utils.config import get_settings

__all__ = ["get_db", "get_engine", "get_session_local"]

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_database_url() -> str:
    url = get_settings().database_url.strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Add it to .env (see .env.example) and run alembic upgrade head."
        )
    return url


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        url = get_database_url()
        connect_args: dict[str, object] = {}
        pool_pre_ping = True
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
            pool_pre_ping = False
        _engine = create_engine(url, pool_pre_ping=pool_pre_ping, connect_args=connect_args)
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


def get_session_local() -> sessionmaker[Session]:
    if _SessionLocal is None:
        get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = get_session_local()()
    try:
        yield db
    finally:
        db.close()
