"""运行监控 HTTP 快照（与 WebSocket 同源数据，便于首屏与断线轮询）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.rbac import ROLE_PLATFORM_ADMIN, ROLE_TSE
from app.services.robot_monitor import compute_robot_metrics

router = APIRouter(prefix="/monitor", tags=["monitor"])


def _require_monitor_role(user: User) -> None:
    if user.role not in (ROLE_PLATFORM_ADMIN, ROLE_TSE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅平台管理员或 TSE 可访问运行监控",
        )


@router.get("/robots")
def monitor_robots_snapshot(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """返回当前数字机器人池态势（与 WS `/api/ws/monitor/robots` 推送结构一致）。"""
    _require_monitor_role(user)
    return compute_robot_metrics(db)
