"""UGC 월드 CRUD — JWT 소유자만 접근, 계정당 월드 수 상한."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...db.models import User, World
from ...db.session import get_db
from ...utils.config import get_settings
from ..deps import get_current_user

router = APIRouter()


def world_to_detail(w: World) -> WorldDetail:
    return WorldDetail(
        id=w.id,
        name=w.name,
        world=w.world_data,
        characters=w.characters_data,
        events=w.events_data,
        created_at=w.created_at,
        updated_at=w.updated_at,
    )


def _validate_payload(world: dict[str, Any], characters: dict[str, Any]) -> None:
    for key in ("id", "name"):
        if key not in world:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"world.{key} is required",
            )
    for key in ("player", "npcs"):
        if key not in characters:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"characters.{key} is required",
            )


class WorldCreateBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    world: dict[str, Any]
    characters: dict[str, Any]
    events: dict[str, Any] | None = None


class WorldUpdateBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    world: dict[str, Any]
    characters: dict[str, Any]
    events: dict[str, Any] | None = None


class WorldSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    world_slug: str = Field(serialization_alias="world_id")
    created_at: datetime

    @classmethod
    def from_orm_world(cls, w: World) -> WorldSummary:
        slug = w.world_data.get("id", "")
        if not isinstance(slug, str):
            slug = str(slug)
        return cls(id=w.id, name=w.name, world_slug=slug, created_at=w.created_at)


class WorldDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    world: dict[str, Any]
    characters: dict[str, Any]
    events: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


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


@router.post("/", response_model=WorldDetail, status_code=status.HTTP_201_CREATED)
def create_world(
    body: WorldCreateBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorldDetail:
    settings = get_settings()
    _validate_payload(body.world, body.characters)
    n = db.scalar(select(func.count(World.id)).where(World.owner_id == user.id))
    if n is not None and n >= settings.max_worlds_per_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"World limit reached ({settings.max_worlds_per_user} per user)",
        )
    w = World(
        owner_id=user.id,
        name=body.name.strip(),
        world_data=body.world,
        characters_data=body.characters,
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
    _validate_payload(body.world, body.characters)
    w.name = body.name.strip()
    w.world_data = body.world
    w.characters_data = body.characters
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
