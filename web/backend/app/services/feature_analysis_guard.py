"""项目功能点分析：测试分析实例占用与并发控制。"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import ProjectFeatureAnalysisRun, RobotInstance
from app.services.robot_catalog import is_analysis_catalog

log = logging.getLogger("app.feature_analysis_guard")


def find_active_feature_analysis_for_instance(
    db: Session,
    robot_instance_id: int,
    *,
    exclude_run_id: int | None = None,
) -> ProjectFeatureAnalysisRun | None:
    q = db.query(ProjectFeatureAnalysisRun).filter(
        ProjectFeatureAnalysisRun.robot_instance_id == robot_instance_id,
        ProjectFeatureAnalysisRun.status.in_(("pending", "running")),
    )
    if exclude_run_id is not None:
        q = q.filter(ProjectFeatureAnalysisRun.id != exclude_run_id)
    return q.order_by(ProjectFeatureAnalysisRun.id.asc()).first()


def feature_analysis_busy_message(busy: ProjectFeatureAnalysisRun) -> str:
    label = "排队中" if busy.status == "pending" else "执行中"
    return (
        f"该测试分析机器人已有功能点分析任务{label}（任务 ID {busy.id}），"
        f"请等待其完成或取消后再发起"
    )


def instance_available_for_feature_analysis(
    db: Session,
    inst: RobotInstance,
) -> tuple[bool, str]:
    if not is_analysis_catalog(inst.catalog_robot_id):
        return False, "该机器人实例不是测试分析类型，不能用于功能点分析"
    if (inst.status or "").strip().lower() != "active":
        return False, "测试分析机器人已停用，请先在「我的机器人」中启用"
    from app.services.analysis_instance_guard import is_instance_generating

    if is_instance_generating(inst.id):
        return False, "该测试分析机器人正在生成用例，请等待完成后再分析"
    busy = find_active_feature_analysis_for_instance(db, inst.id)
    if busy is not None:
        return False, feature_analysis_busy_message(busy)
    return True, ""


def reconcile_stale_feature_analysis_on_startup(db: Session) -> int:
    """服务重启后无内存 worker，将残留的 pending/running 标记为已终止。"""
    stale = (
        db.query(ProjectFeatureAnalysisRun)
        .filter(ProjectFeatureAnalysisRun.status.in_(("pending", "running")))
        .order_by(ProjectFeatureAnalysisRun.id.asc())
        .all()
    )
    if not stale:
        return 0
    now = datetime.utcnow()
    for run in stale:
        run.status = "cancelled"
        run.finished_at = now
        if not (run.output_message or "").strip():
            run.output_message = "服务重启，分析任务已自动终止"
    db.commit()
    ids = [r.id for r in stale]
    log.warning("启动时清理残留功能点分析任务 run_ids=%s", ids)
    return len(stale)
