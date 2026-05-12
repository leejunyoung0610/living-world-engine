"""브라우저 플레이 세션 — 프로세스 메모리. 월드당 1세션(유저별). 재시작 시 소실."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..engine.game_loop import GameEngine


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class PlaySessionBundle:
    engine: GameEngine
    user_id: uuid.UUID
    world_id: uuid.UUID
    created_at: datetime = field(default_factory=_utc_now)
    last_active: datetime = field(default_factory=_utc_now)
    #: 직전 완료 턴의 **시작 시점** 스냅샷(``export_play_payload``). ``/turn/regenerate`` 복원용.
    regenerate_checkpoint: dict[str, Any] | None = None


_lock = threading.Lock()
_sessions: dict[uuid.UUID, PlaySessionBundle] = {}
_by_world: dict[tuple[uuid.UUID, uuid.UUID], uuid.UUID] = {}


def put_session(session_id: uuid.UUID, bundle: PlaySessionBundle) -> None:
    with _lock:
        _sessions[session_id] = bundle
        _by_world[(bundle.user_id, bundle.world_id)] = session_id


def find_session_for_world(user_id: uuid.UUID, world_id: uuid.UUID) -> uuid.UUID | None:
    with _lock:
        return _by_world.get((user_id, world_id))


def take_session(session_id: uuid.UUID, user_id: uuid.UUID) -> PlaySessionBundle | None:
    with _lock:
        b = _sessions.get(session_id)
        if b is None or b.user_id != user_id:
            return None
        b.last_active = _utc_now()
        return b


def list_sessions_for_user(user_id: uuid.UUID) -> list[tuple[uuid.UUID, PlaySessionBundle]]:
    with _lock:
        rows = [(sid, b) for sid, b in _sessions.items() if b.user_id == user_id]
    rows.sort(key=lambda x: x[1].last_active, reverse=True)
    return rows


def remove_session_for_world(user_id: uuid.UUID, world_id: uuid.UUID) -> uuid.UUID | None:
    """해당 유저·월드의 활성 세션 id를 제거하고 반환 (없으면 None)."""
    with _lock:
        sid = _by_world.pop((user_id, world_id), None)
        if sid is not None:
            _sessions.pop(sid, None)
        return sid


def remove_session_by_id(session_id: uuid.UUID) -> PlaySessionBundle | None:
    """세션 id로 제거. 소유 확인은 호출측."""
    with _lock:
        b = _sessions.pop(session_id, None)
        if b is None:
            return None
        key = (b.user_id, b.world_id)
        if _by_world.get(key) == session_id:
            del _by_world[key]
        return b


def clear_all_sessions() -> None:
    """테스트용."""
    with _lock:
        _sessions.clear()
        _by_world.clear()
