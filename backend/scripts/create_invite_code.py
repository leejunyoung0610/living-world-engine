#!/usr/bin/env python3
"""DB에 초대 코드 1건 삽입. 사용: 프로젝트 루트에서
poetry run python backend/scripts/create_invite_code.py BETA-2026-03 --max-uses 5
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

from sqlalchemy import select

from backend.src.db.models.invite_code import InviteCode
from backend.src.db.session import get_session_local


def main() -> None:
    p = argparse.ArgumentParser(description="Create an invite code row (lowercase stored).")
    p.add_argument("code", help="Human-readable code (stored as lowercase, trimmed)")
    p.add_argument("--max-uses", type=int, default=1, dest="max_uses")
    p.add_argument(
        "--expires-at",
        default=None,
        help="ISO8601 UTC e.g. 2026-12-31T23:59:59+00:00 (optional)",
    )
    args = p.parse_args()
    normalized = args.code.strip().lower()
    if not normalized:
        raise SystemExit("code is empty after trim")

    expires = None
    if args.expires_at:
        expires = datetime.fromisoformat(args.expires_at.replace("Z", "+00:00"))
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)

    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        existing = db.scalars(select(InviteCode).where(InviteCode.code == normalized)).first()
        if existing is not None:
            raise SystemExit(f"code already exists: {normalized!r}")
        db.add(
            InviteCode(
                code=normalized,
                max_uses=args.max_uses,
                uses_count=0,
                expires_at=expires,
            )
        )
        db.commit()
        print(f"OK invite_codes.code={normalized!r} max_uses={args.max_uses}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
