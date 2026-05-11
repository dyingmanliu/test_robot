from __future__ import annotations

from typing import Callable, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth_utils import decode_access_token_payload, decode_token
from app.database import get_db
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    raw = creds.credentials
    uid = decode_token(raw)
    if uid is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效或过期的令牌")
    payload = decode_access_token_payload(raw)
    token_role = payload.get("role") if payload else None

    user = db.query(User).filter(User.id == uid).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")

    # JWT 含角色声明时与数据库对齐（网关按 JWT 放行后，服务仍以 DB 为准）
    if token_role is not None and token_role != user.role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="角色已变更，请调用 POST /api/auth/refresh 或重新登录",
        )
    return user


def get_current_user_allow_stale_role(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """仅校验 JWT 主体用户存在；不比对 JWT 内 role 与数据库（供 /auth/refresh 在管理员改角后换新令牌）。"""
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    uid = decode_token(creds.credentials)
    if uid is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效或过期的令牌")
    user = db.query(User).filter(User.id == uid).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return user


def require_roles(*allowed: str) -> Callable[..., User]:
    allowed_set = frozenset(allowed)

    def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_set:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
        return user

    return _check
