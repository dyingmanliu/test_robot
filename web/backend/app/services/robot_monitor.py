"""机器人运行态势聚合。

存在已审批的 ``robot_instances`` 时，按实例展示状态（与 ``test_runs`` 中绑定实例的最新执行关联）；
否则回退为基于环境变量与 ``test_runs`` 的演示池模型。
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import RobotInstance, TestRun


def _compute_robot_metrics_legacy(db: Session) -> dict[str, Any]:
    pool_m = max(0, int(os.getenv("ROBOT_MONITOR_POOL_SIZE", "16")))
    offline_n = max(0, int(os.getenv("ROBOT_MONITOR_OFFLINE_COUNT", "3")))

    running_count = db.query(TestRun).filter(TestRun.status == "running").count()
    pending_count = db.query(TestRun).filter(TestRun.status == "pending").count()

    running_ids = [
        r[0]
        for r in db.query(TestRun.id)
        .filter(TestRun.status == "running")
        .order_by(TestRun.id.asc())
        .limit(pool_m)
        .all()
    ]
    pending_ids = [
        r[0]
        for r in db.query(TestRun.id)
        .filter(TestRun.status == "pending")
        .order_by(TestRun.id.asc())
        .limit(pool_m)
        .all()
    ]

    ex = min(len(running_ids), pool_m)
    rem = pool_m - ex
    wa = min(len(pending_ids), rem)
    idle_c = max(0, pool_m - ex - wa)

    robots: list[dict[str, Any]] = []
    for i in range(ex):
        rid = running_ids[i] if i < len(running_ids) else None
        robots.append(
            {
                "id": f"digital-{i + 1:03d}",
                "name": f"测试数字机器人 {i + 1}",
                "status": "executing",
                "label": "执行中",
                "run_id": rid,
                "instantiated": True,
            }
        )
    for j in range(wa):
        pid = pending_ids[j] if j < len(pending_ids) else None
        idx = ex + j + 1
        robots.append(
            {
                "id": f"digital-{idx:03d}",
                "name": f"测试数字机器人 {idx}",
                "status": "waiting",
                "label": "等待",
                "run_id": pid,
                "instantiated": True,
            }
        )
    base_idx = ex + wa
    for k in range(idle_c):
        idx = base_idx + k + 1
        robots.append(
            {
                "id": f"digital-{idx:03d}",
                "name": f"测试数字机器人 {idx}",
                "status": "idle",
                "label": "待机",
                "run_id": None,
                "instantiated": True,
            }
        )
    for o in range(offline_n):
        robots.append(
            {
                "id": f"edge-offline-{o + 1:02d}",
                "name": f"未接入节点 {o + 1}",
                "status": "offline",
                "label": "离线",
                "run_id": None,
                "instantiated": False,
            }
        )

    now = datetime.now(timezone.utc).isoformat()
    return {
        "type": "robot_monitor",
        "instantiated_count": pool_m,
        "offline_count": offline_n,
        "fleet_display_total": pool_m + offline_n,
        "running_tasks": running_count,
        "pending_tasks": pending_count,
        "executing_slots": ex,
        "waiting_slots": wa,
        "idle_slots": idle_c,
        "robots": robots,
        "online": pool_m,
        "idle": idle_c,
        "executing": ex,
        "waiting": wa,
        "updated_at": now,
        "source": "executor_db+pool_model",
    }


def compute_robot_metrics(db: Session) -> dict[str, Any]:
    instances = (
        db.query(RobotInstance)
        .filter(RobotInstance.status == "active")
        .order_by(RobotInstance.id.asc())
        .all()
    )
    if not instances:
        return _compute_robot_metrics_legacy(db)

    offline_n = max(0, int(os.getenv("ROBOT_MONITOR_OFFLINE_COUNT", "0")))
    running_count = db.query(TestRun).filter(TestRun.status == "running").count()
    pending_count = db.query(TestRun).filter(TestRun.status == "pending").count()

    robots: list[dict[str, Any]] = []
    for inst in instances:
        latest = (
            db.query(TestRun)
            .filter(TestRun.robot_instance_id == inst.id)
            .order_by(desc(TestRun.id))
            .first()
        )
        if latest is not None and latest.status == "running":
            st, label, rid = "executing", "执行中", latest.id
        elif latest is not None and latest.status == "pending":
            st, label, rid = "waiting", "等待", latest.id
        else:
            st, label, rid = "idle", "待机", None

        robots.append(
            {
                "id": inst.instance_code,
                "name": (inst.display_name or "").strip() or inst.catalog_robot_id,
                "status": st,
                "label": label,
                "run_id": rid,
                "instantiated": True,
            }
        )

    for o in range(offline_n):
        robots.append(
            {
                "id": f"edge-offline-{o + 1:02d}",
                "name": f"未接入节点 {o + 1}",
                "status": "offline",
                "label": "离线",
                "run_id": None,
                "instantiated": False,
            }
        )

    ex = sum(1 for r in robots if r["status"] == "executing")
    wa = sum(1 for r in robots if r["status"] == "waiting")
    idle_c = sum(1 for r in robots if r["status"] == "idle")
    pool_m = len(instances)

    now = datetime.now(timezone.utc).isoformat()
    return {
        "type": "robot_monitor",
        "instantiated_count": pool_m,
        "offline_count": offline_n,
        "fleet_display_total": pool_m + offline_n,
        "running_tasks": running_count,
        "pending_tasks": pending_count,
        "executing_slots": ex,
        "waiting_slots": wa,
        "idle_slots": idle_c,
        "robots": robots,
        "online": pool_m,
        "idle": idle_c,
        "executing": ex,
        "waiting": wa,
        "updated_at": now,
        "source": "robot_instances+test_runs",
    }
