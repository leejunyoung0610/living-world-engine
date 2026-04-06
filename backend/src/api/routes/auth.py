"""회원가입·로그인 MVP — PostgreSQL + JWT."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db.models import User
from ...db.session import get_db
from ...utils.config import get_settings
from ..deps import get_current_user_email

router = APIRouter()


class SignupBody(BaseModel):
    email: EmailStr
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=8, max_length=128)
    invite_code: str = Field(default="", max_length=80)


class LoginBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserPublic(BaseModel):
    email: str
    username: str


def _create_access_token(email: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": email,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(body: SignupBody, db: Session = Depends(get_db)) -> dict[str, str]:
    """`invite_code` 필드는 수용만 함 (검증은 Week 2에서 연결 가능)."""
    email = body.email.lower()
    existing = db.scalars(select(User).where(User.email == email)).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    hashed = bcrypt.hashpw(body.password.encode("utf-8"), bcrypt.gensalt())
    db.add(User(email=email, username=body.username, password_hash=hashed))
    db.commit()
    return {"message": "created", "email": email}


@router.post("/login", response_model=TokenResponse)
def login(body: LoginBody, db: Session = Depends(get_db)) -> TokenResponse:
    email = body.email.lower()
    user = db.scalars(select(User).where(User.email == email)).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not bcrypt.checkpw(
        body.password.encode("utf-8"),
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = _create_access_token(email)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserPublic)
def me(
    email: str = Depends(get_current_user_email),
    db: Session = Depends(get_db),
) -> UserPublic:
    user = db.scalars(select(User).where(User.email == email)).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserPublic(email=email, username=user.username)
