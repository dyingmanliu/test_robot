from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.auth_utils import create_access_token, hash_password, verify_password
from app.database import get_db
from app.deps import get_current_user, get_current_user_allow_stale_role
from app.models import PersonalSpace, Project, User
from app.rbac import ROLE_ENTERPRISE
from app.schemas import ChangePasswordBody, LoginBody, ProfileUpdate, RegisterBody, Token, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _new_username() -> str:
    return "u" + uuid.uuid4().hex[:12]


def _resolve_user(db: Session, account: str) -> Optional[User]:
    raw = account.strip()
    if not raw:
        return None
    if "@" in raw:
        em = raw.lower().strip()
        u = db.query(User).filter(User.email == em).first()
        if u is not None:
            return u
    digits = "".join(c for c in raw if c.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        u = db.query(User).filter(User.phone == digits).first()
        if u is not None:
            return u
    return db.query(User).filter(User.username == raw).first()


@router.post("/register", response_model=UserOut)
def register(body: RegisterBody, db: Session = Depends(get_db)) -> User:
    if body.phone:
        if db.query(User).filter(User.phone == body.phone).first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该手机号已注册")
        user = User(
            username=_new_username(),
            phone=body.phone,
            hashed_password=hash_password(body.password),
            role=ROLE_ENTERPRISE,
        )
    else:
        email_norm = str(body.email).strip().lower()
        if db.query(User).filter(User.email == email_norm).first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该邮箱已注册")
        user = User(
            username=_new_username(),
            email=email_norm,
            hashed_password=hash_password(body.password),
            role=ROLE_ENTERPRISE,
        )

    db.add(user)
    db.flush()
    db.add(PersonalSpace(user_id=user.id, name="个人空间"))
    db.add(
        Project(
            owner_id=user.id,
            name="默认项目空间",
            tested_app_name="未指定",
            test_objective="",
        )
    )
    db.commit()
    loaded = (
        db.query(User)
        .options(joinedload(User.personal_space))
        .filter(User.id == user.id)
        .first()
    )
    assert loaded is not None
    return loaded


@router.post("/login", response_model=Token)
def login(body: LoginBody, db: Session = Depends(get_db)) -> Token:
    user = _resolve_user(db, body.account)
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")
    return Token(access_token=create_access_token(user.id, user.role))


@router.post("/refresh", response_model=Token)
def refresh_token(user: User = Depends(get_current_user_allow_stale_role)) -> Token:
    """角色变更后刷新 JWT，使网关与客户端获得最新 `role` 声明。"""
    return Token(access_token=create_access_token(user.id, user.role))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    u = db.query(User).options(joinedload(User.personal_space)).filter(User.id == user.id).first()
    return u if u is not None else user


@router.patch("/profile", response_model=UserOut)
def update_profile(
    body: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    u = db.query(User).options(joinedload(User.personal_space)).filter(User.id == user.id).first()
    if u is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    data = body.model_dump(exclude_unset=True)
    for key in ("nickname", "avatar_url", "company"):
        if key in data:
            setattr(u, key, data[key])
    db.commit()
    db.refresh(u)
    return u


@router.post("/change-password")
def change_password(
    body: ChangePasswordBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    u = db.query(User).filter(User.id == user.id).first()
    if u is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    if not verify_password(body.old_password, u.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前密码不正确")
    u.hashed_password = hash_password(body.new_password)
    db.commit()
    return {"detail": "密码已更新"}
