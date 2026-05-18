"""UGC 월드 CRUD — JWT 소유자만 접근, 계정당 월드 수 상한."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...db.models import PlaySession, User, World, WorldUserLike
from ...db.session import get_db
from ...utils.config import get_settings
from ...worlds.genre_catalog import GENRE_DEFINITIONS, normalize_genres
from ..deps import get_current_user

router = APIRouter()

WorldVisibility = Literal["private", "public"]


def _genres_from_model(w: World) -> list[str]:
    raw = w.genres
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for x in raw:
        if isinstance(x, str) and x.strip():
            out.append(x.strip())
    return out


def world_to_detail(w: World) -> WorldDetail:
    return WorldDetail(
        id=w.id,
        name=w.name,
        visibility=w.visibility if w.visibility in ("private", "public") else "private",
        world=w.world_data,
        characters=w.characters_data,
        events=w.events_data,
        genres=_genres_from_model(w),
        created_at=w.created_at,
        updated_at=w.updated_at,
    )


def _validate_world(world: dict[str, Any]) -> None:
    for key in ("id", "name"):
        if key not in world:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"world.{key} is required",
            )


class WorldCharactersBody(BaseModel):
    """`npcs` 기본 `[]`. `player`·`quests` 등은 `extra='allow'`로 허용하나 저장 시 `player`는 제거됨."""

    model_config = ConfigDict(extra="allow")

    npcs: list[Any] = Field(default_factory=list)


def _normalize_characters_for_storage(characters: dict[str, Any]) -> dict[str, Any]:
    """UGC 월드에는 NPC(및 선택 quests)만 저장. 플레이어는 플레이 시작 시 합성."""
    npcs = characters.get("npcs")
    out: dict[str, Any] = {"npcs": npcs if isinstance(npcs, list) else []}
    q = characters.get("quests")
    if isinstance(q, list):
        out["quests"] = q
    return out


def _parse_genres_for_save(raw: list[str]) -> list[str]:
    try:
        return normalize_genres(raw, min_count=1)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="장르는 허용된 슬러그 중 최소 1개 필요합니다.",
        ) from None


class WorldCreateBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    world: dict[str, Any]
    characters: WorldCharactersBody
    events: dict[str, Any] | None = None
    visibility: WorldVisibility = "private"
    genres: list[str] = Field(min_length=1)

    @field_validator("genres", mode="before")
    @classmethod
    def _strip_genres(cls, v: object) -> object:
        if v is None:
            return []
        return v


class WorldUpdateBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    world: dict[str, Any]
    characters: WorldCharactersBody
    events: dict[str, Any] | None = None
    visibility: WorldVisibility = "private"
    genres: list[str] = Field(min_length=1)

    @field_validator("genres", mode="before")
    @classmethod
    def _strip_genres(cls, v: object) -> object:
        if v is None:
            return []
        return v


class WorldSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    visibility: WorldVisibility
    world_slug: str = Field(serialization_alias="world_id")
    genres: list[str] = Field(default_factory=list)
    created_at: datetime

    @classmethod
    def from_orm_world(cls, w: World) -> WorldSummary:
        slug = w.world_data.get("id", "")
        if not isinstance(slug, str):
            slug = str(slug)
        vis: WorldVisibility = (
            w.visibility if w.visibility in ("private", "public") else "private"
        )
        return cls(
            id=w.id,
            name=w.name,
            visibility=vis,
            world_slug=slug,
            genres=_genres_from_model(w),
            created_at=w.created_at,
        )


class WorldDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    visibility: WorldVisibility
    world: dict[str, Any]
    characters: dict[str, Any]
    events: dict[str, Any] | None
    genres: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ExploreWorldSummary(BaseModel):
    """탐색 — 공개 월드만."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    world_slug: str = Field(serialization_alias="world_id")
    owner_username: str
    is_mine: bool
    genres: list[str] = Field(default_factory=list)
    play_start_count: int = 0
    like_count: int = 0
    liked_by_me: bool = False
    created_at: datetime
    updated_at: datetime


class PublicNpcBrief(BaseModel):
    """공개 상세 — NPC 이름·역할·한 줄 요약(성격/배경 등)."""

    name: str
    role: str = ""
    location: str = ""
    summary: str = ""


class PublicWorldDetail(BaseModel):
    """공개 월드 브라우징용 — 스포일 최소(설정·소개 위주)."""

    id: uuid.UUID
    name: str
    world_slug: str = Field(serialization_alias="world_id")
    owner_username: str
    is_mine: bool
    genres: list[str] = Field(default_factory=list)
    description: str = ""
    world_setting: str = ""
    time_label: str = Field(default="", serialization_alias="time")
    npc_count: int = 0
    npcs: list[PublicNpcBrief] = Field(default_factory=list)
    play_start_count: int = 0
    like_count: int = 0
    liked_by_me: bool = False
    created_at: datetime
    updated_at: datetime


class WorldLikeState(BaseModel):
    liked: bool
    like_count: int


class ExploreWorldsPage(BaseModel):
    items: list[ExploreWorldSummary]
    total: int
    limit: int
    offset: int


class GenreEntry(BaseModel):
    slug: str
    label: str


def _get_owned_world(db: Session, world_id: uuid.UUID, owner_id: uuid.UUID) -> World | None:
    return db.scalars(
        select(World).where(World.id == world_id, World.owner_id == owner_id)
    ).first()


def _public_blurbs(wd: dict[str, Any]) -> tuple[str, str, str]:
    """(description, world_setting, time)."""
    desc = wd.get("description")
    desc_s = desc.strip() if isinstance(desc, str) else ""
    setting = ""
    raw_ws = wd.get("world_setting")
    if isinstance(raw_ws, str) and raw_ws.strip():
        setting = raw_ws.strip()
    elif isinstance(raw_ws, list):
        parts = [str(x).strip() for x in raw_ws if isinstance(x, str) and str(x).strip()]
        setting = "\n\n".join(parts)
    leg = wd.get("setting")
    if not setting and isinstance(leg, str) and leg.strip():
        setting = leg.strip()
    wt = wd.get("time")
    time_s = wt.strip() if isinstance(wt, str) else ""
    return desc_s, setting, time_s


def _npc_count(chars: dict[str, Any]) -> int:
    npcs = chars.get("npcs")
    return len(npcs) if isinstance(npcs, list) else 0


def _public_npc_briefs(
    chars: dict[str, Any],
    *,
    max_npcs: int = 48,
    summary_max: int = 280,
) -> list[PublicNpcBrief]:
    npcs_raw = chars.get("npcs")
    if not isinstance(npcs_raw, list):
        return []
    out: list[PublicNpcBrief] = []
    for raw in npcs_raw[:max_npcs]:
        if not isinstance(raw, dict):
            continue
        name_v = raw.get("name")
        if not isinstance(name_v, str) or not name_v.strip():
            continue
        role_v = raw.get("role")
        role_s = role_v.strip() if isinstance(role_v, str) else ""
        loc_v = raw.get("location")
        loc_s = loc_v.strip() if isinstance(loc_v, str) else ""
        major_v = raw.get("major")
        if isinstance(major_v, str) and major_v.strip():
            if not role_s:
                role_s = major_v.strip()
            elif major_v.strip() not in role_s:
                role_s = f"{role_s} · {major_v.strip()}"
        summary = ""
        for key in ("personality", "background", "description"):
            v = raw.get(key)
            if isinstance(v, str) and v.strip():
                summary = v.strip()
                break
        if len(summary) > summary_max:
            summary = summary[: summary_max - 1] + "…"
        out.append(
            PublicNpcBrief(
                name=name_v.strip(),
                role=role_s,
                location=loc_s,
                summary=summary,
            )
        )
    return out


def _user_preferred_genre_slugs(db: Session, user_id: uuid.UUID) -> set[str]:
    pws = db.scalars(
        select(PlaySession.world_id)
        .where(PlaySession.user_id == user_id)
        .order_by(PlaySession.updated_at.desc())
        .limit(12)
    ).all()
    if not pws:
        return set()
    worlds = db.scalars(select(World).where(World.id.in_(pws))).all()
    pref: set[str] = set()
    for w in worlds:
        for g in _genres_from_model(w):
            pref.add(g)
    return pref


ExploreSort = Literal["latest", "popular", "recommended"]


@router.get("/meta/genres", response_model=list[GenreEntry])
def list_genre_meta() -> list[GenreEntry]:
    """장르 슬러그·라벨 (월드 생성·필터 UI용, 인증 불필요)."""
    return [GenreEntry(slug=s, label=L) for s, L in GENRE_DEFINITIONS]


@router.get("/", response_model=list[WorldSummary])
def list_worlds(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WorldSummary]:
    rows = db.scalars(select(World).where(World.owner_id == user.id).order_by(World.created_at)).all()
    return [WorldSummary.from_orm_world(w) for w in rows]


@router.get("/explore", response_model=ExploreWorldsPage)
def explore_worlds(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort: ExploreSort = Query(default="latest"),
    genre: str | None = Query(default=None, description="장르 슬러그 1개 — 해당 장르가 포함된 월드만"),
    q: str | None = Query(default=None, description="월드 이름 부분 검색"),
) -> ExploreWorldsPage:
    public = World.visibility == "public"
    stmt = (
        select(World, User.username)
        .join(User, World.owner_id == User.id)
        .where(public)
    )
    if q and q.strip():
        stmt = stmt.where(World.name.ilike(f"%{q.strip()}%"))
    rows = list(db.execute(stmt).all())

    if genre and genre.strip():
        gslug = genre.strip().lower()
        rows = [(w, un) for w, un in rows if gslug in _genres_from_model(w)]

    pref = _user_preferred_genre_slugs(db, user.id) if sort == "recommended" else set()

    def overlap_score(w: World) -> int:
        if not pref:
            return 0
        ws = set(_genres_from_model(w))
        return len(pref & ws)

    def sort_key(t: tuple[World, Any]) -> tuple[Any, ...]:
        w, _ = t
        updated = w.updated_at or datetime.now(timezone.utc)
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        pop = int(getattr(w, "play_start_count", 0) or 0)
        ts = -updated.timestamp()
        if sort == "popular":
            return (-pop, ts)
        if sort == "recommended":
            if pref:
                ov = overlap_score(w)
                return (-ov, -pop, ts)
            # 플레이 이력이 없을 때는 인기순과 겹치지 않도록 최신·발견 위주
            return (ts, -pop)
        return (ts,)

    rows.sort(key=sort_key)
    total = len(rows)
    page = rows[offset : offset + limit]

    page_ids = [w.id for w, _ in page]
    liked_ids: set[uuid.UUID] = set()
    if page_ids:
        liked_rows = db.scalars(
            select(WorldUserLike.world_id).where(
                WorldUserLike.user_id == user.id,
                WorldUserLike.world_id.in_(page_ids),
            )
        ).all()
        liked_ids = set(liked_rows)

    out: list[ExploreWorldSummary] = []
    for w, owner_username in page:
        slug = w.world_data.get("id", "")
        if not isinstance(slug, str):
            slug = str(slug)
        out.append(
            ExploreWorldSummary(
                id=w.id,
                name=w.name,
                world_slug=slug,
                owner_username=str(owner_username),
                is_mine=w.owner_id == user.id,
                genres=_genres_from_model(w),
                play_start_count=int(getattr(w, "play_start_count", 0) or 0),
                like_count=int(getattr(w, "like_count", 0) or 0),
                liked_by_me=w.id in liked_ids,
                created_at=w.created_at,
                updated_at=w.updated_at,
            )
        )
    return ExploreWorldsPage(items=out, total=total, limit=limit, offset=offset)


@router.get("/public/{world_id}", response_model=PublicWorldDetail)
def get_public_world_detail(
    world_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PublicWorldDetail:
    row = db.execute(
        select(World, User.username)
        .join(User, World.owner_id == User.id)
        .where(World.id == world_id, World.visibility == "public")
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found")
    w, owner_username = row[0], row[1]
    wd = w.world_data if isinstance(w.world_data, dict) else {}
    desc, setting, time_s = _public_blurbs(wd)
    slug = wd.get("id", "")
    if not isinstance(slug, str):
        slug = str(slug)
    liked = (
        db.scalars(
            select(WorldUserLike).where(
                WorldUserLike.world_id == world_id,
                WorldUserLike.user_id == user.id,
            )
        ).first()
        is not None
    )
    chars = w.characters_data if isinstance(w.characters_data, dict) else {}
    return PublicWorldDetail(
        id=w.id,
        name=w.name,
        world_slug=slug,
        owner_username=str(owner_username),
        is_mine=w.owner_id == user.id,
        genres=_genres_from_model(w),
        description=desc,
        world_setting=setting,
        time_label=time_s,
        npc_count=_npc_count(chars),
        npcs=_public_npc_briefs(chars),
        play_start_count=int(getattr(w, "play_start_count", 0) or 0),
        like_count=int(getattr(w, "like_count", 0) or 0),
        liked_by_me=liked,
        created_at=w.created_at,
        updated_at=w.updated_at,
    )


@router.post("/{world_id}/like", response_model=WorldLikeState)
def toggle_world_like(
    world_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorldLikeState:
    w = db.get(World, world_id)
    if w is None or w.visibility != "public":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found")
    existing = db.scalars(
        select(WorldUserLike).where(
            WorldUserLike.world_id == world_id,
            WorldUserLike.user_id == user.id,
        )
    ).first()
    if existing is not None:
        db.delete(existing)
        w.like_count = max(0, int(w.like_count or 0) - 1)
        liked = False
    else:
        db.add(WorldUserLike(world_id=world_id, user_id=user.id))
        w.like_count = int(w.like_count or 0) + 1
        liked = True
    db.commit()
    db.refresh(w)
    return WorldLikeState(liked=liked, like_count=int(w.like_count or 0))


@router.post("/", response_model=WorldDetail, status_code=status.HTTP_201_CREATED)
def create_world(
    body: WorldCreateBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorldDetail:
    settings = get_settings()
    _validate_world(body.world)
    chars_raw = body.characters.model_dump(mode="python", exclude_none=False)
    genres_save = _parse_genres_for_save(list(body.genres))
    n = db.scalar(select(func.count(World.id)).where(World.owner_id == user.id))
    if n is not None and n >= settings.max_worlds_per_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"World limit reached ({settings.max_worlds_per_user} per user)",
        )
    w = World(
        owner_id=user.id,
        name=body.name.strip(),
        visibility=body.visibility,
        world_data=body.world,
        characters_data=_normalize_characters_for_storage(chars_raw),
        events_data=body.events,
        genres=genres_save,
        play_start_count=0,
        like_count=0,
    )
    db.add(w)
    db.commit()
    db.refresh(w)
    return world_to_detail(w)


@router.get("/{world_id}", response_model=WorldDetail)
def get_world(
    world_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorldDetail:
    w = _get_owned_world(db, world_id, user.id)
    if w is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found")
    return world_to_detail(w)


@router.put("/{world_id}", response_model=WorldDetail)
def update_world(
    world_id: uuid.UUID,
    body: WorldUpdateBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorldDetail:
    w = _get_owned_world(db, world_id, user.id)
    if w is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found")
    _validate_world(body.world)
    chars_raw = body.characters.model_dump(mode="python", exclude_none=False)
    genres_save = _parse_genres_for_save(list(body.genres))
    w.name = body.name.strip()
    w.visibility = body.visibility
    w.world_data = body.world
    w.characters_data = _normalize_characters_for_storage(chars_raw)
    w.events_data = body.events
    w.genres = genres_save
    db.commit()
    db.refresh(w)
    return world_to_detail(w)


@router.delete("/{world_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_world(
    world_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    w = _get_owned_world(db, world_id, user.id)
    if w is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found")
    db.delete(w)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
