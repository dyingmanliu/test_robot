"""同一机器人实例同时仅允许一个 pending/running 的 test_run。"""

from __future__ import annotations

import threading
from typing import Optional

from sqlalchemy.orm import Session

from app.models import TestRun

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


def busy_run_detail_message(busy: TestRun) -> str:
    label = "排队中" if busy.status == "pending" else "执行中"
    return (
        f"该机器人实例已有任务{label}（运行 ID {busy.id}），"
        f"请等待其完成或终止后再执行新用例"
    )
