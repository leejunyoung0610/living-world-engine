"""브라우저 플레이 — DB 월드로 GameEngine 세션."""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db.models import User, World
from ...db.session import get_db
from ...engine.dialogue_split import split_assistant_into_segments
from ...engine.game_loop import GameEngine
from ...services import play_sessions
from ...utils.config import PROJECT_ROOT
from ...utils.logger import get_logger
from ..deps import get_current_user

router = APIRouter()
logger = get_logger(__name__)

PLAY_SESSIONS_DIR = PROJECT_ROOT / "data" / "play_sessions"


class PlayStartBody(BaseModel):
    world_id: uuid.UUID
    force_new: bool = False


class PlayStartResponse(BaseModel):
    session_id: uuid.UUID
    world_name: str
    resumed: bool = False


class SessionSummary(BaseModel):
    session_id: uuid.UUID
    world_id: uuid.UUID
    world_name: str
    turn: int
    day: int
    last_message_preview: str = ""
    created_at: datetime
    last_active: datetime


class TurnBody(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class NpcLineSegment(BaseModel):
    speaker: str
    text: str


class TurnResponse(BaseModel):
    turn: int
    day: int
    response: str
    response_segments: list[NpcLineSegment] = Field(default_factory=list)
    events_triggered: list[dict[str, str]]


class PlayHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    segments: list[NpcLineSegment] = Field(default_factory=list)


class PlayHistoryResponse(BaseModel):
    turn: int
    day: int
    world_name: str
    messages: list[PlayHistoryMessage]


def _memory_file(session_id: uuid.UUID) -> Path:
    return PLAY_SESSIONS_DIR / f"{session_id}.json"


def _delete_memory_file(session_id: uuid.UUID) -> None:
    p = _memory_file(session_id)
    if p.exists():
        try:
            p.unlink()
        except OSError:
            logger.warning("play memory file delete failed: %s", p)


def _playable_world(db: Session, world_id: uuid.UUID, user_id: uuid.UUID) -> World | None:
    """소유 월드이거나 공개(``public``) 월드면 플레이 가능."""
    w = db.scalars(select(World).where(World.id == world_id)).first()
    if w is None:
        return None
    if w.owner_id == user_id:
        return w
    if getattr(w, "visibility", "private") == "public":
        return w
    return None


def _npc_names_from_engine(engine: Any) -> list[str]:
    state = getattr(engine, "state", None)
    if state is None:
        return []
    npcs = getattr(state, "npcs", None) or []
    out: list[str] = []
    for n in npcs:
        if isinstance(n, dict) and n.get("name"):
            out.append(str(n["name"]))
    return out


def _segments_for_assistant(engine: Any, content: str) -> list[NpcLineSegment]:
    raw = split_assistant_into_segments(content, _npc_names_from_engine(engine))
    return [NpcLineSegment(speaker=s["speaker"], text=s["text"]) for s in raw]


def _last_message_preview(engine: Any) -> str:
    hist = getattr(engine, "conversation_history", None) or []
    if not hist:
        return ""
    last = hist[-1]
    role = last.get("role")
    content = str(last.get("content", ""))
    if role == "user":
        t = content.strip().replace("\n", " ")
        return (t[:80] + "…") if len(t) > 80 else t
    segs = split_assistant_into_segments(content, _npc_names_from_engine(engine))
    if not segs:
        return ""
    s0 = segs[0]
    line = f"{s0['speaker']}: {s0['text']}".strip().replace("\n", " ")
    return (line[:100] + "…") if len(line) > 100 else line


@router.get("/sessions", response_model=list[SessionSummary])
def list_play_sessions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SessionSummary]:
    rows = play_sessions.list_sessions_for_user(user.id)
    if not rows:
        return []

    world_ids = {b.world_id for _, b in rows}
    worlds = db.scalars(select(World).where(World.id.in_(world_ids))).all()
    name_by_wid = {w.id: w.name for w in worlds}

    out: list[SessionSummary] = []
    for sid, bundle in rows:
        eng = bundle.engine
        st = getattr(eng, "state", None)
        turn = int(getattr(st, "turn", 0) or 0)
        day = int(getattr(st, "day", 1) or 1)
        out.append(
            SessionSummary(
                session_id=sid,
                world_id=bundle.world_id,
                world_name=name_by_wid.get(bundle.world_id, ""),
                turn=turn,
                day=day,
                last_message_preview=_last_message_preview(eng),
                created_at=bundle.created_at,
                last_active=bundle.last_active,
            )
        )
    return out


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def play_delete_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
) -> Response:
    b = play_sessions.take_session(session_id, user.id)
    if b is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    play_sessions.remove_session_by_id(session_id)
    _delete_memory_file(session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{session_id}/history", response_model=PlayHistoryResponse)
def play_history(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlayHistoryResponse:
    bundle = play_sessions.take_session(session_id, user.id)
    if bundle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    world = db.scalars(select(World).where(World.id == bundle.world_id)).first()
    world_name = world.name if world else ""

    eng = bundle.engine
    turn = int(getattr(getattr(eng, "state", None), "turn", 0) or 0)
    day = int(getattr(getattr(eng, "state", None), "day", 1) or 1)
    hist = getattr(eng, "conversation_history", None) or []

    messages: list[PlayHistoryMessage] = []
    for m in hist:
        role = m.get("role")
        content = str(m.get("content", ""))
        if role == "user":
            messages.append(PlayHistoryMessage(role="user", content=content, segments=[]))
        elif role == "assistant":
            segs = _segments_for_assistant(eng, content)
            messages.append(
                PlayHistoryMessage(role="assistant", content=content, segments=segs)
            )

    return PlayHistoryResponse(turn=turn, day=day, world_name=world_name, messages=messages)


@router.post("/start")
def play_start(
    body: PlayStartBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    w = _playable_world(db, body.world_id, user.id)
    if w is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found")

    if body.force_new:
        old_sid = play_sessions.remove_session_for_world(user.id, w.id)
        if old_sid is not None:
            _delete_memory_file(old_sid)
    else:
        existing_sid = play_sessions.find_session_for_world(user.id, w.id)
        if existing_sid is not None:
            bundle = play_sessions.take_session(existing_sid, user.id)
            if bundle is not None:
                payload = PlayStartResponse(
                    session_id=existing_sid,
                    world_name=w.name,
                    resumed=True,
                ).model_dump(mode="json")
                return JSONResponse(status_code=status.HTTP_200_OK, content=payload)

    session_id = uuid.uuid4()
    PLAY_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    mem_path = _memory_file(session_id)

    engine = GameEngine()
    try:
        engine.initialize_from_dicts(
            w.world_data,
            w.characters_data,
            w.events_data,
            memory_storage_path=mem_path,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e

    play_sessions.put_session(
        session_id,
        play_sessions.PlaySessionBundle(
            engine=engine,
            user_id=user.id,
            world_id=w.id,
        ),
    )
    payload = PlayStartResponse(
        session_id=session_id,
        world_name=w.name,
        resumed=False,
    ).model_dump(mode="json")
    return JSONResponse(status_code=status.HTTP_201_CREATED, content=payload)


@router.post("/{session_id}/turn", response_model=TurnResponse)
def play_turn(
    session_id: uuid.UUID,
    body: TurnBody,
    user: User = Depends(get_current_user),
) -> TurnResponse:
    bundle = play_sessions.take_session(session_id, user.id)
    if bundle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    try:
        result = bundle.engine.process_turn(body.message.strip())
    except Exception as exc:
        logger.exception("play turn failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM 또는 엔진 처리 중 오류가 났습니다. API 키·네트워크를 확인하세요.",
        ) from exc

    ev = result.get("events_triggered") or []
    safe_events: list[dict[str, str]] = []
    for e in ev:
        if isinstance(e, dict):
            safe_events.append(
                {
                    "event_id": str(e.get("event_id", "")),
                    "description": str(e.get("description", "")),
                }
            )

    response_text = str(result.get("response", ""))
    segs = _segments_for_assistant(bundle.engine, response_text)

    return TurnResponse(
        turn=int(result.get("turn", 0)),
        day=int(result.get("day", 1)),
        response=response_text,
        response_segments=segs,
        events_triggered=safe_events,
    )
