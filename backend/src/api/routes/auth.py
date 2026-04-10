"""회원가입·로그인 MVP — PostgreSQL + JWT."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...db.models import InviteCode, User
from ...db.session import get_db
from ...utils.config import get_settings
from ..deps import get_current_user_email

router = APIRouter()


def _normalize_invite_code(raw: str) -> str:
    return raw.strip().lower()


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
    """`invite_code`: `require_invite_code_for_signup` 가 켜져 있을 때만 DB 검증."""
    settings = get_settings()
    email = body.email.lower()
    existing = db.scalars(select(User).where(User.email == email)).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user_total = db.scalar(select(func.count()).select_from(User)) or 0
    cap = settings.max_total_users
    if cap is not None and int(user_total) >= cap:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="가입 가능 인원이 가득 찼습니다.",
        )

    invite: InviteCode | None = None
    if settings.require_invite_code_for_signup:
        normalized = _normalize_invite_code(body.invite_code)
        if not normalized:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="초대 코드를 입력해 주세요.",
            )
        invite = db.scalars(
            select(InviteCode).where(InviteCode.code == normalized),
        ).first()
        if invite is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="유효하지 않은 초대 코드입니다.",
            )
        now = datetime.now(timezone.utc)
        if invite.expires_at is not None and invite.expires_at < now:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="만료된 초대 코드입니다.",
            )
        if invite.uses_count >= invite.max_uses:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="이 초대 코드는 더 이상 사용할 수 없습니다.",
            )

    hashed = bcrypt.hashpw(body.password.encode("utf-8"), bcrypt.gensalt())
    db.add(User(email=email, username=body.username, password_hash=hashed))
    if invite is not None:
        invite.uses_count += 1
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
