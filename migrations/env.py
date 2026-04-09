"""Alembic 환경 — `DATABASE_URL`·`Base.metadata` 사용."""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context
from dotenv import load_dotenv

# 프로젝트 루트 (alembic.ini 기준)
ROOT = Path(__file__).resolve().parent.parent
# Alembic만: 프로젝트 .env가 셸의 빈 DATABASE_URL 등보다 우선 (override=True)
_env_file = ROOT / ".env"
if _env_file.is_file():
    load_dotenv(_env_file, override=True)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.src.db.base import Base  # noqa: E402
from backend.src.db.models import PlaySession, User, World  # noqa: E402, F401
from backend.src.utils.config import get_settings  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if not url:
        url = get_settings().database_url.strip()
    if not url:
        raise RuntimeError(
            f"DATABASE_URL is not set. Add {_env_file} with DATABASE_URL=..., "
            "or: DATABASE_URL='postgresql://…' poetry run python -m alembic upgrade head"
        )
    return url


def run_migrations_offline() -> None:
    url = _database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
