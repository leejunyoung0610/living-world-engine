"""UGC 월드 CRUD — JWT 소유자만 접근, 계정당 월드 수 상한."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...db.models import User, World
from ...db.session import get_db
from ...utils.config import get_settings
from ..deps import get_current_user

router = APIRouter()

WorldVisibility = Literal["private", "public"]


def world_to_detail(w: World) -> WorldDetail:
    return WorldDetail(
        id=w.id,
        name=w.name,
        visibility=w.visibility if w.visibility in ("private", "public") else "private",
        world=w.world_data,
        characters=w.characters_data,
        events=w.events_data,
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


class WorldCreateBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    world: dict[str, Any]
    characters: WorldCharactersBody
    events: dict[str, Any] | None = None
    visibility: WorldVisibility = "private"


class WorldUpdateBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    world: dict[str, Any]
    characters: WorldCharactersBody
    events: dict[str, Any] | None = None
    visibility: WorldVisibility = "private"


class WorldSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    visibility: WorldVisibility
    world_slug: str = Field(serialization_alias="world_id")
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
    created_at: datetime
    updated_at: datetime


class ExploreWorldsPage(BaseModel):
    items: list[ExploreWorldSummary]
    total: int
    limit: int
    offset: int


def _get_owned_world(db: Session, world_id: uuid.UUID, owner_id: uuid.UUID) -> World | None:
    return db.scalars(
        select(World).where(World.id == world_id, World.owner_id == owner_id)
    ).first()


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
) -> ExploreWorldsPage:
    public = World.visibility == "public"
    total = int(db.scalar(select(func.count()).select_from(World).where(public)) or 0)
    rows = db.execute(
        select(World, User.username)
        .join(User, World.owner_id == User.id)
        .where(public)
        .order_by(World.updated_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    out: list[ExploreWorldSummary] = []
    for w, owner_username in rows:
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
    w.name = body.name.strip()
    w.visibility = body.visibility
    w.world_data = body.world
    w.characters_data = _normalize_characters_for_storage(chars_raw)
    w.events_data = body.events
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
