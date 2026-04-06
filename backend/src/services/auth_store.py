"""인메모리 사용자 저장소 — PostgreSQL 전환 전 MVP/테스트용."""

from __future__ import annotations

import threading
from typing import Any

_lock = threading.Lock()
_users: dict[str, dict[str, Any]] = {}


def clear() -> None:
    with _lock:
        _users.clear()


def add_user(email: str, username: str, password_hash: bytes) -> None:
    with _lock:
        if email in _users:
            raise ValueError("email_taken")
        _users[email] = {"username": username, "password_hash": password_hash}


def get_user(email: str) -> dict[str, Any] | None:
    with _lock:
        u = _users.get(email)
        return dict(u) if u else None
