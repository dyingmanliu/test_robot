"""同一机器人实例同时仅允许一个 pending/running 的 test_run。"""

from __future__ import annotations

import logging
import threading
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import TestRun

log = logging.getLogger(__name__)

ACTIVE_RUN_STATUSES = ("pending", "running")

_instance_locks_guard = threading.Lock()
_instance_locks: dict[int, threading.Lock] = {}


def instance_execution_lock(robot_instance_id: int) -> threading.Lock:
    with _instance_locks_guard:
        lock = _instance_locks.get(robot_instance_id)
        if lock is None:
            lock = threading.Lock()
            _instance_locks[robot_instance_id] = lock
        return lock


def find_active_run_for_instance(
    db: Session,
    robot_instance_id: int,
    *,
    exclude_run_id: int | None = None,
) -> TestRun | None:
    q = db.query(TestRun).filter(
        TestRun.robot_instance_id == robot_instance_id,
        TestRun.status.in_(ACTIVE_RUN_STATUSES),
    )
    if exclude_run_id is not None:
        q = q.filter(TestRun.id != exclude_run_id)
    return q.order_by(TestRun.id.asc()).first()


def instance_available_for_run(db: Session, inst: RobotInstance) -> tuple[bool, str]:
    """是否允许提交新用例执行（实例已启动且当前空闲）。"""
    if (inst.status or "").strip().lower() != "active":
        return False, "机器人实例已停用，请先在管理端启用后再执行用例"
    busy = find_active_run_for_instance(db, inst.id)
    if busy is not None:
        return False, busy_run_detail_message(busy)
    return True, ""


def resolve_instance_runtime_status(db: Session, inst: RobotInstance) -> str:
    """实例运行态：executing | idle | abnormal（供「我的机器人」列表展示）。"""
    if (inst.status or "").strip().lower() != "active":
        return "abnormal"
    if find_active_run_for_instance(db, inst.id) is not None:
        return "executing"
    return "idle"


def busy_run_detail_message(busy: TestRun) -> str:
    label = "排队中" if busy.status == "pending" else "执行中"
    return (
        f"该机器人实例已有任务{label}（运行 ID {busy.id}），"
        f"请等待其完成或终止后再执行新用例"
    )


def reconcile_stale_runs_on_startup(db: Session) -> int:
    """服务重启后无内存 worker，将残留的 pending/running 标记为已终止。"""
    stale = (
        db.query(TestRun)
        .filter(TestRun.status.in_(ACTIVE_RUN_STATUSES))
        .order_by(TestRun.id.asc())
        .all()
    )
    if not stale:
        return 0
    now = datetime.utcnow()
    for run in stale:
        run.status = "cancelled"
        run.finished_at = now
        if not (run.output_message or "").strip():
            run.output_message = "服务重启，任务已自动终止"
    db.commit()
    ids = [r.id for r in stale]
    log.warning("启动时清理残留执行任务 run_ids=%s", ids)
    return len(stale)
