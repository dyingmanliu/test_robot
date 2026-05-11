"""大屏监控：WebSocket 实时推送机器人态势（鉴权后订阅）。"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.auth_utils import decode_token
from app.database import SessionLocal
from app.models import User
from app.rbac import ROLE_PLATFORM_ADMIN, ROLE_TSE
from app.services.robot_monitor import compute_robot_metrics

router = APIRouter()

PUSH_INTERVAL_SEC = 2.0

log = logging.getLogger(__name__)


@router.websocket("/ws/monitor/robots")
async def robot_monitor_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    token = websocket.query_params.get("token") or ""
    uid = decode_token(token.strip())
    if uid is None:
        log.info("ws monitor: reject missing or invalid token")
        await websocket.send_json({"type": "error", "detail": "未登录或令牌无效"})
        await websocket.close(code=1008)
        return

    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.id == uid).first()
        if user is None or user.role not in (ROLE_PLATFORM_ADMIN, ROLE_TSE):
            log.info(
                "ws monitor: reject uid=%s role=%s (need admin or tse)",
                uid,
                getattr(user, "role", None),
            )
            await websocket.send_json({"type": "error", "detail": "仅平台管理员或 TSE 可订阅大屏监控"})
            await websocket.close(code=1008)
            return
    finally:
        db.close()

    log.info("ws monitor: subscribe uid=%s role=%s", uid, user.role)
    try:
        while True:
            db = SessionLocal()
            try:
                payload = compute_robot_metrics(db)
            finally:
                db.close()
            await websocket.send_json(payload)
            await asyncio.sleep(PUSH_INTERVAL_SEC)
    except WebSocketDisconnect:
        log.info("ws monitor: disconnect uid=%s", uid)
        return
    except Exception:
        log.exception("ws monitor: stream error uid=%s", uid)
        raise
