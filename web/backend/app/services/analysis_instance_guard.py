"""测试分析机器人：用例生成占用与并发控制（进程内，对齐 test_run 单实例互斥）。"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.orm import Session

from app.models import RobotInstance
from app.services.robot_catalog import is_analysis_catalog
from app.services.robot_run_guard import find_active_run_for_instance

_guard = threading.Lock()
_generating_ids: set[int] = set()


def is_instance_generating(robot_instance_id: int) -> bool:
    with _guard:
        return robot_instance_id in _generating_ids


def reset_generation_locks_on_startup() -> None:
    """进程重启后清空内存占用标记（无存活 worker 时）。"""
    with _guard:
        _generating_ids.clear()


@contextmanager
def analysis_generation_lock(robot_instance_id: int) -> Iterator[None]:
    with _guard:
        if robot_instance_id in _generating_ids:
            raise RuntimeError("analysis_instance_busy")
        _generating_ids.add(robot_instance_id)
    try:
        yield
    finally:
        with _guard:
            _generating_ids.discard(robot_instance_id)


def instance_available_for_generation(db: Session, inst: RobotInstance) -> tuple[bool, str]:
    if not is_analysis_catalog(inst.catalog_robot_id):
        return False, "该机器人实例不是测试分析类型，不能用于自动生成用例"
    if (inst.status or "").strip().lower() != "active":
        return False, "测试分析机器人已停用，请先在管理端或「我的机器人」中启用后再生成用例"
    busy_run = find_active_run_for_instance(db, inst.id)
    if busy_run is not None:
        return False, "该测试分析机器人正在执行其他任务，请稍后再试"
    if is_instance_generating(inst.id):
        return False, "该测试分析机器人正在生成用例，请等待当前任务完成后再试"
    from app.services.feature_analysis_guard import (
        feature_analysis_busy_message,
        find_active_feature_analysis_for_instance,
    )

    busy_fa = find_active_feature_analysis_for_instance(db, inst.id)
    if busy_fa is not None:
        return False, feature_analysis_busy_message(busy_fa)
    return True, ""
