"""平台管理员：用户与角色管理（RBAC）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_roles
from app.models import User
from app.rbac import ROLE_PLATFORM_ADMIN, ROLE_LABELS, ROLES
from app.schemas import AdminRolePatch, AdminUserOut

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[AdminUserOut])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(ROLE_PLATFORM_ADMIN)),
) -> list[User]:
    return db.query(User).order_by(User.id.desc()).all()


@router.get("/rbac/roles", response_model=dict[str, str])
def list_role_definitions(
    _: User = Depends(require_roles(ROLE_PLATFORM_ADMIN)),
) -> dict[str, str]:
    """预定义角色说明，供管理端展示。"""
    return {r: ROLE_LABELS.get(r, r) for r in ROLES}


@router.patch("/users/{user_id}/role", response_model=AdminUserOut)
def set_user_role(
    user_id: int,
    body: AdminRolePatch,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(ROLE_PLATFORM_ADMIN)),
) -> User:
    if user_id == admin.id and body.role != ROLE_PLATFORM_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能自行取消平台管理员角色",
        )
    u = db.query(User).filter(User.id == user_id).first()
    if u is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    u.role = body.role
    db.commit()
    db.refresh(u)
    return u
