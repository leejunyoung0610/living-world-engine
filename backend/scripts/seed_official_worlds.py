#!/usr/bin/env python3
"""``backend/src/worlds/<slug>/{world,characters,events}.json`` 을 DB 의 공개 월드로 upsert.

운영팀(시스템) 유저 1명을 만들고, 그 유저 소유의 ``visibility="public"`` 월드로 등록한다.
시스템 유저는 ``password_hash=None``, ``auth_provider="system"`` 으로 로그인 불가능 상태.

사용 예 (docker compose 환경)::

    docker compose exec api poetry run python backend/scripts/seed_official_worlds.py
    docker compose exec api poetry run python backend/scripts/seed_official_worlds.py --slug campus
    docker compose exec api poetry run python backend/scripts/seed_official_worlds.py --force

호스트 환경에서 직접 ``DATABASE_URL`` 로도 실행 가능.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.db.models import User, World
from backend.src.db.session import get_session_local

WORLDS_ROOT = Path(__file__).resolve().parents[1] / "src" / "worlds"
SYSTEM_EMAIL = "system@platform.local"

# 공식 폴더 슬러그 → DB ``worlds.genres`` (장르 슬러그 배열)
OFFICIAL_WORLD_GENRES: dict[str, list[str]] = {
    "arcane_academy": ["fantasy", "academy", "adventure"],
    "campus": ["academy", "slice_of_life", "romance"],
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _ensure_system_user(db: Session, *, username: str) -> User:
    u = db.scalars(select(User).where(User.email == SYSTEM_EMAIL)).first()
    if u is None:
        u = User(
            email=SYSTEM_EMAIL,
            username=username,
            password_hash=None,
            auth_provider="system",
        )
        db.add(u)
        db.flush()
    elif u.username != username:
        u.username = username
    return u


def _normalize_characters(chars: dict[str, Any]) -> dict[str, Any]:
    """플레이어 정보를 제거 — UGC 월드와 동일한 저장 규칙."""
    out: dict[str, Any] = {"npcs": chars.get("npcs") or []}
    if isinstance(chars.get("quests"), list):
        out["quests"] = chars["quests"]
    return out


def _seed_world(db: Session, owner: User, slug: str, *, force: bool) -> str:
    base = WORLDS_ROOT / slug
    world_path = base / "world.json"
    if not world_path.exists():
        return f"  ! {slug}: world.json 없음 — 건너뜀"

    world_data = _load_json(world_path)
    chars_path = base / "characters.json"
    chars_data = (
        _normalize_characters(_load_json(chars_path)) if chars_path.exists() else {"npcs": []}
    )
    ev_path = base / "events.json"
    events_data: dict[str, Any] | None = _load_json(ev_path) if ev_path.exists() else None

    name = str(world_data.get("name") or slug)

    genres = OFFICIAL_WORLD_GENRES.get(slug, ["fantasy"])

    # 이름 기준 매칭 — JSON 인덱싱은 DB 별로 다르므로 단순화.
    existing = db.scalars(
        select(World).where(World.owner_id == owner.id, World.name == name)
    ).first()

    if existing is not None and force:
        db.delete(existing)
        db.flush()
        existing = None

    if existing is None:
        db.add(
            World(
                owner_id=owner.id,
                name=name,
                visibility="public",
                world_data=world_data,
                characters_data=chars_data,
                events_data=events_data,
                genres=genres,
                play_start_count=0,
            )
        )
        return f"  + {slug}: created → {name!r}"

    existing.world_data = world_data
    existing.characters_data = chars_data
    existing.events_data = events_data
    existing.visibility = "public"
    existing.genres = genres
    return f"  ~ {slug}: updated → {name!r}"


def main() -> None:
    p = argparse.ArgumentParser(description="공식 월드 시드 (system 유저 소유, public)")
    p.add_argument(
        "--slug",
        default=None,
        help="단일 슬러그만 시드 (예: campus). 미지정 시 worlds/* 전체.",
    )
    p.add_argument(
        "--owner-username",
        default="운영팀",
        help="system 유저 username (기본: 운영팀)",
    )
    p.add_argument("--force", action="store_true", help="기존 row 삭제 후 재생성")
    args = p.parse_args()

    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        owner = _ensure_system_user(db, username=args.owner_username)
        print(f"system user: id={owner.id} email={owner.email} username={owner.username}")

        if args.slug:
            slugs = [args.slug]
        else:
            slugs = sorted(p.name for p in WORLDS_ROOT.iterdir() if p.is_dir())

        for slug in slugs:
            print(_seed_world(db, owner, slug, force=args.force))

        db.commit()
        print("done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
