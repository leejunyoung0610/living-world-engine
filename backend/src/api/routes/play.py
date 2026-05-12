"""브라우저 플레이 — DB 월드로 GameEngine 세션 (진행 DB 영속화)."""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import json

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db.models import User, World
from ...db.session import get_db
from ...engine.dialogue_split import split_assistant_into_segments
from ...engine.game_loop import GameEngine
from ...engine.play_persistence import (
    apply_play_payload,
    export_play_payload,
    strip_nested_regenerate_checkpoint,
    sync_engine_after_restore,
)
from ...services import platform_cost
from ...services import play_session_db
from ...services import play_sessions
from ...services import turn_quota
from ...utils.config import PROJECT_ROOT, get_settings
from ...utils.logger import get_logger
from ..deps import get_current_user
from ..limiter import limiter

router = APIRouter()
logger = get_logger(__name__)

PLAY_SESSIONS_DIR = PROJECT_ROOT / "data" / "play_sessions"


class PlayStartBody(BaseModel):
    world_id: uuid.UUID
    force_new: bool = False
    #: 새 세션 시작 시 필수(이어하기 응답 경로에서는 생략).
    player: dict[str, Any] | None = None


class PlayStartResponse(BaseModel):
    session_id: uuid.UUID
    world_name: str
    resumed: bool = False


class PlayWorldBriefResponse(BaseModel):
    """플레이 입장 화면용 — 공개·소유 월드 조회."""

    world_uuid: uuid.UUID
    list_name: str
    story_title: str
    description: str = ""
    #: 스토리용 상세 세계관 (`world_setting`; 없으면 레거시 `setting` 등).
    world_setting: str = ""
    npcs: list[dict[str, Any]] = Field(default_factory=list)
    suggested_player: dict[str, Any] | None = None  # 구버전 월드에만 있을 수 있음


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


class RegenerateStreamBody(BaseModel):
    """재생성 스트림 선택 본문 — `message`가 있으면 마지막 플레이어 대사를 이 내용으로 바꿔 다시 실행."""

    message: str | None = Field(default=None, min_length=1, max_length=4000)


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
    #: 화자 분할 알고리즘이 클라이언트에서 점진 분할(스트리밍 중 화자 블록)에 사용한다.
    npc_names: list[str] = Field(default_factory=list)


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


def _validate_entry_player(player: dict[str, Any]) -> None:
    name = player.get("name")
    if not isinstance(name, str) or not name.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="player.name is required",
        )


def _merge_template_and_entry_player(
    template_chars: dict[str, Any],
    player: dict[str, Any],
) -> dict[str, Any]:
    npcs_raw = template_chars.get("npcs")
    npcs: list[Any] = npcs_raw if isinstance(npcs_raw, list) else []
    merged: dict[str, Any] = {"player": deepcopy(player), "npcs": deepcopy(npcs)}
    q = template_chars.get("quests")
    if isinstance(q, list):
        merged["quests"] = deepcopy(q)
    pl = merged["player"]
    st = pl.get("stats")
    if st is None:
        pl["stats"] = {}
    elif not isinstance(st, dict):
        pl["stats"] = {}
    if not pl.get("class"):
        pl["class"] = "traveler"
    return merged


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


def _ensure_platform_llm_key(engine: Any) -> None:
    """모든 플레이는 서버 `ANTHROPIC_API_KEY` 단일 키로 LLM 호출."""
    llm = getattr(engine, "llm", None)
    if llm is None or not hasattr(llm, "rebind_api_key"):
        return
    settings = get_settings()
    if not settings.anthropic_api_key.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="플랫폼 API 키(ANTHROPIC_API_KEY)가 설정되지 않았습니다. 관리자에게 문의하세요.",
        )
    engine.llm.rebind_api_key(None)


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


def _build_engine_from_world_row(world: World, row: Any) -> GameEngine:
    mem_path = _memory_file(row.id)
    eng = GameEngine()
    eng.initialize_from_dicts(
        world.world_data,
        world.characters_data,
        world.events_data,
        memory_storage_path=mem_path,
    )
    apply_play_payload(eng, row.payload)
    sync_engine_after_restore(eng)
    return eng


def _ensure_bundle(
    db: Session, session_id: uuid.UUID, user_id: uuid.UUID
) -> play_sessions.PlaySessionBundle | None:
    b = play_sessions.take_session(session_id, user_id)
    if b is not None:
        return b
    row = play_session_db.get_row_by_id_user(db, session_id, user_id)
    if row is None:
        return None
    world = db.get(World, row.world_id)
    if world is None:
        return None
    eng = _build_engine_from_world_row(world, row)
    bundle = play_sessions.PlaySessionBundle(
        engine=eng,
        user_id=user_id,
        world_id=row.world_id,
        created_at=row.created_at,
        last_active=datetime.now(timezone.utc),
    )
    _hydrate_regenerate_checkpoint(bundle, row.payload)
    play_sessions.put_session(session_id, bundle)
    return play_sessions.take_session(session_id, user_id)


def _hydrate_regenerate_checkpoint(
    bundle: play_sessions.PlaySessionBundle, payload: Any
) -> None:
    pl = payload if isinstance(payload, dict) else {}
    rc = pl.get("regenerate_checkpoint")
    if isinstance(rc, dict) and rc.get("world_state"):
        bundle.regenerate_checkpoint = rc


def _persist_session(
    db: Session,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    world_id: uuid.UUID,
    engine: Any,
    *,
    bundle: play_sessions.PlaySessionBundle | None = None,
) -> None:
    play_session_db.upsert_play_session(
        db,
        session_id,
        user_id,
        world_id,
        engine,
        last_preview=_last_message_preview(engine),
        regenerate_checkpoint=bundle.regenerate_checkpoint if bundle else None,
    )


def _brief_world_setting(wd: dict[str, Any]) -> str:
    raw = wd.get("world_setting")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    if isinstance(raw, list):
        parts = [str(x).strip() for x in raw if isinstance(x, str) and str(x).strip()]
        if parts:
            return "\n\n".join(parts)
    leg = wd.get("setting")
    if isinstance(leg, str) and leg.strip():
        return leg.strip()
    return ""


@router.get("/world/{world_id}/brief", response_model=PlayWorldBriefResponse)
def play_world_brief(
    world_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlayWorldBriefResponse:
    """입장 화면 — 탐색·타유저 플레이 시 월드 메타·NPC 목록 (소유/공개만)."""
    w = _playable_world(db, world_id, user.id)
    if w is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found")
    wd = w.world_data if isinstance(w.world_data, dict) else {}
    chars = w.characters_data if isinstance(w.characters_data, dict) else {}
    npcs_raw = chars.get("npcs")
    npcs_list: list[dict[str, Any]] = (
        [x for x in npcs_raw if isinstance(x, dict)] if isinstance(npcs_raw, list) else []
    )
    sug = chars.get("player") if isinstance(chars.get("player"), dict) else None
    return PlayWorldBriefResponse(
        world_uuid=w.id,
        list_name=w.name,
        story_title=str(wd.get("name", "") or ""),
        description=str(wd.get("description", "") or ""),
        world_setting=_brief_world_setting(wd),
        npcs=npcs_list,
        suggested_player=sug,
    )


@router.get("/sessions", response_model=list[SessionSummary])
def list_play_sessions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SessionSummary]:
    rows = play_session_db.list_rows_for_user(db, user.id)
    if not rows:
        return []

    world_ids = {r.world_id for r in rows}
    worlds = db.scalars(select(World).where(World.id.in_(world_ids))).all()
    name_by_wid = {w.id: w.name for w in worlds}

    out: list[SessionSummary] = []
    for r in rows:
        out.append(
            SessionSummary(
                session_id=r.id,
                world_id=r.world_id,
                world_name=name_by_wid.get(r.world_id, ""),
                turn=int(r.turn),
                day=int(r.day),
                last_message_preview=r.last_preview or "",
                created_at=r.created_at,
                last_active=r.updated_at,
            )
        )
    return out


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def play_delete_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    b = play_sessions.remove_session_by_id(session_id)
    deleted_db = play_session_db.delete_row_by_id_user(db, session_id, user.id)
    if b is None and not deleted_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    _delete_memory_file(session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{session_id}/history", response_model=PlayHistoryResponse)
def play_history(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlayHistoryResponse:
    bundle = _ensure_bundle(db, session_id, user.id)
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

    return PlayHistoryResponse(
        turn=turn,
        day=day,
        world_name=world_name,
        messages=messages,
        npc_names=_npc_names_from_engine(eng),
    )


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
        db_sid = play_session_db.delete_row_by_user_world(db, user.id, w.id)
        mem_sid = play_sessions.remove_session_for_world(user.id, w.id)
        for sid in {x for x in (db_sid, mem_sid) if x is not None}:
            _delete_memory_file(sid)
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

        row = play_session_db.get_row_by_user_world(db, user.id, w.id)
        if row is not None:
            eng = _build_engine_from_world_row(w, row)
            bundle = play_sessions.PlaySessionBundle(
                engine=eng,
                user_id=user.id,
                world_id=w.id,
                created_at=row.created_at,
                last_active=datetime.now(timezone.utc),
            )
            _hydrate_regenerate_checkpoint(bundle, row.payload)
            play_sessions.put_session(row.id, bundle)
            payload = PlayStartResponse(
                session_id=row.id,
                world_name=w.name,
                resumed=True,
            ).model_dump(mode="json")
            return JSONResponse(status_code=status.HTTP_200_OK, content=payload)

    session_id = uuid.uuid4()
    PLAY_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    mem_path = _memory_file(session_id)

    if body.player is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="이 월드로 새로 들어가려면 player(입장 캐릭터) JSON이 필요합니다.",
        )
    _validate_entry_player(body.player)
    template_chars = w.characters_data if isinstance(w.characters_data, dict) else {}
    characters_merged = _merge_template_and_entry_player(template_chars, body.player)

    engine = GameEngine()
    try:
        engine.initialize_from_dicts(
            w.world_data,
            characters_merged,
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
    bundle = play_sessions.take_session(session_id, user.id)
    if bundle is None:
        raise HTTPException(status_code=500, detail="세션 등록 실패")
    bundle.regenerate_checkpoint = strip_nested_regenerate_checkpoint(
        export_play_payload(engine)
    )
    _persist_session(db, session_id, user.id, w.id, engine, bundle=bundle)

    payload = PlayStartResponse(
        session_id=session_id,
        world_name=w.name,
        resumed=False,
    ).model_dump(mode="json")
    return JSONResponse(status_code=status.HTTP_201_CREATED, content=payload)


@limiter.limit("90/minute")
@router.post("/{session_id}/turn", response_model=TurnResponse)
def play_turn(
    request: Request,
    session_id: uuid.UUID,
    body: TurnBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TurnResponse:
    bundle = _ensure_bundle(db, session_id, user.id)
    if bundle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    settings = get_settings()
    db.refresh(user)
    if settings.emergency_shutdown:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="긴급 점검 중입니다. 플레이가 일시 중단되었습니다.",
        )

    _ensure_platform_llm_key(bundle.engine)

    turn_quota.check_platform_turn_quota_or_raise(db, user, settings)

    ut = getattr(bundle.engine, "usage_tracker", None)
    cost_before = float(ut.total_cost) if ut is not None else 0.0

    bundle.regenerate_checkpoint = strip_nested_regenerate_checkpoint(
        export_play_payload(bundle.engine)
    )

    try:
        result = bundle.engine.process_turn(body.message.strip())
    except Exception as exc:
        logger.exception("play turn failed")
        detail = "LLM 또는 엔진 처리 중 오류가 났습니다. API 키·네트워크를 확인하세요."
        if get_settings().debug:
            detail = f"{detail} ({type(exc).__name__}: {exc})"
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail,
        ) from exc

    turn_quota.record_platform_turn(db, user, settings)
    if ut is not None:
        delta = float(ut.total_cost) - cost_before
        platform_cost.record_platform_cost_delta(db, delta, settings)

    _persist_session(db, session_id, user.id, bundle.world_id, bundle.engine, bundle=bundle)

    ev = result.get("events_triggered") or []
    safe_events: list[dict[str, str]] = []
    for e in ev:
        if isinstance(e, dict):
            safe_events.append(
                {
                    "event_id": str(e.get("event_id", "")),
                    "description": str(e.get("description", "")),
                    "narrative_hint": str(e.get("narrative_hint", "")),
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


def _sse_event(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@limiter.limit("90/minute")
@router.post("/{session_id}/turn/stream")
def play_turn_stream(
    request: Request,
    session_id: uuid.UUID,
    body: TurnBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    bundle = _ensure_bundle(db, session_id, user.id)
    if bundle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    settings = get_settings()
    db.refresh(user)
    if settings.emergency_shutdown:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="긴급 점검 중입니다. 플레이가 일시 중단되었습니다.",
        )

    _ensure_platform_llm_key(bundle.engine)
    turn_quota.check_platform_turn_quota_or_raise(db, user, settings)

    ut = getattr(bundle.engine, "usage_tracker", None)
    cost_before = float(ut.total_cost) if ut is not None else 0.0
    bundle.regenerate_checkpoint = strip_nested_regenerate_checkpoint(
        export_play_payload(bundle.engine)
    )
    msg = body.message.strip()

    def _generate() -> Any:
        final_result: dict[str, Any] | None = None
        try:
            for ev in bundle.engine.process_turn_stream(msg):
                if ev.get("type") == "delta":
                    text = ev.get("text") or ""
                    if text:
                        yield _sse_event("delta", {"text": text})
                elif ev.get("type") == "done":
                    final_result = ev.get("result")

            if final_result is None:
                yield _sse_event("error", {"detail": "엔진이 응답을 반환하지 못했습니다."})
                return

            turn_quota.record_platform_turn(db, user, settings)
            if ut is not None:
                delta = float(ut.total_cost) - cost_before
                platform_cost.record_platform_cost_delta(db, delta, settings)
            _persist_session(db, session_id, user.id, bundle.world_id, bundle.engine, bundle=bundle)

            response_text = str(final_result.get("response", ""))
            segs = _segments_for_assistant(bundle.engine, response_text)
            ev_list = final_result.get("events_triggered") or []
            safe_events: list[dict[str, str]] = []
            for e in ev_list:
                if isinstance(e, dict):
                    safe_events.append(
                        {
                            "event_id": str(e.get("event_id", "")),
                            "description": str(e.get("description", "")),
                            "narrative_hint": str(e.get("narrative_hint", "")),
                        }
                    )

            done_payload = {
                "turn": int(final_result.get("turn", 0)),
                "day": int(final_result.get("day", 1)),
                "response": response_text,
                "response_segments": [s.model_dump() for s in segs],
                "events_triggered": safe_events,
            }
            yield _sse_event("done", done_payload)
        except Exception as exc:
            logger.exception("play turn stream failed")
            detail = "스트리밍 처리 중 오류가 났습니다. 네트워크/API 키를 확인하세요."
            if get_settings().debug:
                detail = f"{detail} ({type(exc).__name__}: {exc})"
            yield _sse_event("error", {"detail": detail})

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return StreamingResponse(_generate(), media_type="text/event-stream", headers=headers)


@limiter.limit("90/minute")
@router.post("/{session_id}/turn/regenerate/stream")
def play_regenerate_stream(
    request: Request,
    session_id: uuid.UUID,
    body: RegenerateStreamBody = Body(default_factory=RegenerateStreamBody),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """마지막 NPC 응답만 다시 생성. 턴 직전 스냅샷으로 상태를 되돌린 뒤 사용자 메시지(본문에 주면 교체)로 스트림 재실행."""
    bundle = _ensure_bundle(db, session_id, user.id)
    if bundle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    settings = get_settings()
    db.refresh(user)
    if settings.emergency_shutdown:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="긴급 점검 중입니다. 플레이가 일시 중단되었습니다.",
        )

    _ensure_platform_llm_key(bundle.engine)

    cp = bundle.regenerate_checkpoint
    if not isinstance(cp, dict) or not cp.get("world_state"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="재생성할 수 있는 이전 상태가 없습니다. 메시지를 한 번 더 보낸 뒤 다시 시도해 주세요.",
        )

    hist = bundle.engine.conversation_history
    if (
        len(hist) < 2
        or hist[-1].get("role") != "assistant"
        or hist[-2].get("role") != "user"
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="마지막 메시지가 플레이어 다음 NPC 응답이 아니면 재생성할 수 없습니다.",
        )
    user_msg = str(hist[-2].get("content", "")).strip()
    if not user_msg:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="빈 사용자 메시지는 재생성할 수 없습니다.",
        )

    replacement: str | None = None
    if body.message is not None:
        replacement = body.message.strip()
        if not replacement:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="바꿀 플레이어 대사가 비어 있으면 안 됩니다.",
            )
    effective_msg = replacement if replacement is not None else user_msg

    apply_play_payload(bundle.engine, cp)
    sync_engine_after_restore(bundle.engine)

    turn_quota.check_platform_turn_quota_or_raise(db, user, settings)

    ut = getattr(bundle.engine, "usage_tracker", None)
    cost_before = float(ut.total_cost) if ut is not None else 0.0

    bundle.regenerate_checkpoint = strip_nested_regenerate_checkpoint(
        export_play_payload(bundle.engine)
    )

    def _generate() -> Any:
        final_result: dict[str, Any] | None = None
        try:
            for ev in bundle.engine.process_turn_stream(effective_msg):
                if ev.get("type") == "delta":
                    text = ev.get("text") or ""
                    if text:
                        yield _sse_event("delta", {"text": text})
                elif ev.get("type") == "done":
                    final_result = ev.get("result")

            if final_result is None:
                yield _sse_event("error", {"detail": "엔진이 응답을 반환하지 못했습니다."})
                return

            turn_quota.record_platform_turn(db, user, settings)
            if ut is not None:
                delta = float(ut.total_cost) - cost_before
                platform_cost.record_platform_cost_delta(db, delta, settings)
            _persist_session(db, session_id, user.id, bundle.world_id, bundle.engine, bundle=bundle)

            response_text = str(final_result.get("response", ""))
            segs = _segments_for_assistant(bundle.engine, response_text)
            ev_list = final_result.get("events_triggered") or []
            safe_events: list[dict[str, str]] = []
            for e in ev_list:
                if isinstance(e, dict):
                    safe_events.append(
                        {
                            "event_id": str(e.get("event_id", "")),
                            "description": str(e.get("description", "")),
                            "narrative_hint": str(e.get("narrative_hint", "")),
                        }
                    )

            done_payload = {
                "turn": int(final_result.get("turn", 0)),
                "day": int(final_result.get("day", 1)),
                "response": response_text,
                "response_segments": [s.model_dump() for s in segs],
                "events_triggered": safe_events,
            }
            yield _sse_event("done", done_payload)
        except Exception as exc:
            logger.exception("play regenerate stream failed")
            detail = "재생성 스트리밍 중 오류가 났습니다. 네트워크/API 키를 확인하세요."
            if get_settings().debug:
                detail = f"{detail} ({type(exc).__name__}: {exc})"
            yield _sse_event("error", {"detail": detail})

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return StreamingResponse(_generate(), media_type="text/event-stream", headers=headers)
