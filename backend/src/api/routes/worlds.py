"""UGC 월드 CRUD — JWT 소유자만 접근, 계정당 월드 수 상한."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...db.models import PlaySession, User, World
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
    created_at: datetime
    updated_at: datetime


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
        if sort == "popular":
            return (-pop, -updated.timestamp())
        if sort == "recommended":
            ov = overlap_score(w)
            return (-ov, -pop, -updated.timestamp())
        return (-updated.timestamp(),)

    rows.sort(key=sort_key)
    total = len(rows)
    page = rows[offset : offset + limit]

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
                created_at=w.created_at,
                updated_at=w.updated_at,
            )
        )
    return ExploreWorldsPage(items=out, total=total, limit=limit, offset=offset)


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
