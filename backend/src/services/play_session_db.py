"""플레이 세션 PostgreSQL 영속화."""

from __future__ import annotations

import uuid
from copy import deepcopy
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db.models import PlaySession
from ..engine.game_loop import GameEngine
from ..engine.play_persistence import export_play_payload, strip_nested_regenerate_checkpoint


def upsert_play_session(
    db: Session,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    world_id: uuid.UUID,
    engine: GameEngine,
    *,
    last_preview: str,
    regenerate_checkpoint: dict[str, Any] | None = None,
) -> None:
    blob = export_play_payload(engine)
    if regenerate_checkpoint is not None:
        blob["regenerate_checkpoint"] = strip_nested_regenerate_checkpoint(
            deepcopy(regenerate_checkpoint)
        )
    else:
        blob.pop("regenerate_checkpoint", None)
    row = db.get(PlaySession, session_id)
    if row is None:
        row = PlaySession(
            id=session_id,
            user_id=user_id,
            world_id=world_id,
            payload=blob,
            turn=engine.state.turn,
            day=engine.state.day,
            last_preview=last_preview or None,
        )
        db.add(row)
    else:
        row.user_id = user_id
        row.world_id = world_id
        row.payload = blob
        row.turn = engine.state.turn
        row.day = engine.state.day
        row.last_preview = last_preview or None
    db.commit()


def get_row_by_user_world(
    db: Session, user_id: uuid.UUID, world_id: uuid.UUID
) -> PlaySession | None:
    return db.scalars(
        select(PlaySession).where(
            PlaySession.user_id == user_id,
            PlaySession.world_id == world_id,
        )
    ).first()


def get_row_by_id_user(
    db: Session, session_id: uuid.UUID, user_id: uuid.UUID
) -> PlaySession | None:
    return db.scalars(
        select(PlaySession).where(
            PlaySession.id == session_id,
            PlaySession.user_id == user_id,
        )
    ).first()


def list_rows_for_user(db: Session, user_id: uuid.UUID) -> list[PlaySession]:
    return list(
        db.scalars(
            select(PlaySession)
            .where(PlaySession.user_id == user_id)
            .order_by(PlaySession.updated_at.desc())
        ).all()
    )


def delete_row_by_user_world(
    db: Session, user_id: uuid.UUID, world_id: uuid.UUID
) -> uuid.UUID | None:
    row = get_row_by_user_world(db, user_id, world_id)
    if row is None:
        return None
    sid = row.id
    db.delete(row)
    db.commit()
    return sid


def delete_row_by_id_user(
    db: Session, session_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    row = get_row_by_id_user(db, session_id, user_id)
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def delete_all_play_sessions(db: Session) -> None:
    """테스트용."""
    db.execute(delete(PlaySession))
    db.commit()
