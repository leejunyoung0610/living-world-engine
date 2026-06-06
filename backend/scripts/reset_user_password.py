#!/usr/bin/env python3
"""로컬·개발용 — 사용자 비밀번호 재설정 (bcrypt).

사용 (프로젝트 루트):
  poetry run python backend/scripts/reset_user_password.py EMAIL NEW_PASSWORD
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bcrypt
from sqlalchemy import select

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.src.db.models import User  # noqa: E402
from backend.src.db.session import get_session_local  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="Reset user password (local dev)")
    p.add_argument("email")
    p.add_argument("password", help="New plaintext password (hashed before save)")
    args = p.parse_args()

    email = args.email.strip().lower()
    if not email or "@" not in email:
        raise SystemExit("Invalid email")
    if len(args.password) < 8:
        raise SystemExit("Password must be at least 8 characters")

    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        user = db.scalars(select(User).where(User.email == email)).first()
        if user is None:
            raise SystemExit(f"User not found: {email}")
        user.password_hash = bcrypt.hashpw(args.password.encode("utf-8"), bcrypt.gensalt())
        if user.auth_provider in (None, ""):
            user.auth_provider = "local"
        db.commit()
        print(f"OK: password updated for {email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
