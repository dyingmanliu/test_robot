"""项目空间看板：从执行记录、报告、缺陷等模块聚合度量（数据服务逻辑）。"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Defect, ProjectReport, TestCase, TestRun
from app.services.run_metrics import count_recognition_steps


def build_project_dashboard_payload(db: Session, project_id: int) -> dict[str, Any]:
    """聚合项目维度指标：执行任务数、报告摘要、活跃机器人、未关闭缺陷趋势。"""
    total_task_runs = (
        db.query(TestRun).join(TestCase, TestRun.case_id == TestCase.id).filter(TestCase.project_id == project_id).count()
    )

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    runs_last_30_days = (
        db.query(TestRun)
        .join(TestCase, TestRun.case_id == TestCase.id)
        .filter(TestCase.project_id == project_id)
        .filter(
            or_(
                TestRun.started_at >= thirty_days_ago,
                TestRun.finished_at >= thirty_days_ago,
            )
        )
        .count()
    )

    latest = (
        db.query(ProjectReport)
        .filter(ProjectReport.project_id == project_id)
        .order_by(ProjectReport.created_at.desc())
        .first()
    )
    latest_report: dict[str, Any]
    if latest is None:
        latest_report = {
            "summary": None,
            "generated_at": None,
            "placeholder": True,
            "hint": "接入报告流水线后可写入 project_reports；或由数据服务聚合外部报告摘要",
        }
    else:
        latest_report = {
            "summary": latest.summary,
            "generated_at": latest.created_at.isoformat(),
            "placeholder": False,
        }

    last_activity = (
        db.query(TestRun.finished_at)
        .join(TestCase, TestRun.case_id == TestCase.id)
        .filter(TestCase.project_id == project_id)
        .filter(TestRun.finished_at.isnot(None))
        .order_by(TestRun.finished_at.desc())
        .limit(1)
        .scalar()
    )
    active_robots = [
        {
            "id": "autoglm-phone",
            "name": "手机端 UI 自动化（数字机器人）",
            "last_used_at": last_activity.isoformat() if last_activity else None,
            "catalog_note": "与模型执行记录联动；多机器人时可扩展列表",
        }
    ]

    now = datetime.utcnow()
    labels: list[str] = []
    open_backlog: list[int] = []
    for offset in range(13, -1, -1):
        day = (now.date() - timedelta(days=offset))
        end_of_day = datetime.combine(day, datetime.max.time())
        labels.append(day.strftime("%m-%d"))
        n = (
            db.query(Defect)
            .filter(
                Defect.project_id == project_id,
                Defect.created_at <= end_of_day,
                or_(Defect.resolved_at.is_(None), Defect.resolved_at > end_of_day),
            )
            .count()
        )
        open_backlog.append(n)

    runs_for_project = (
        db.query(TestRun, TestCase)
        .join(TestCase, TestRun.case_id == TestCase.id)
        .filter(TestCase.project_id == project_id)
        .all()
    )
    success_runs = sum(1 for r, _ in runs_for_project if r.status == "success")
    failed_runs = sum(1 for r, _ in runs_for_project if r.status == "failed")
    cancelled_runs = sum(1 for r, _ in runs_for_project if r.status == "cancelled")
    pending_running_runs = sum(1 for r, _ in runs_for_project if r.status in ("pending", "running"))
    total_recognition_steps = sum(count_recognition_steps(r.step_log) for r, _ in runs_for_project)

    case_stats: dict[int, dict[str, Any]] = defaultdict(
        lambda: {"case_id": 0, "title": "", "run_count": 0, "success_count": 0, "recognition_steps": 0}
    )
    for r, tc in runs_for_project:
        cid = tc.id
        entry = case_stats[cid]
        entry["case_id"] = cid
        entry["title"] = tc.title
        entry["run_count"] += 1
        if r.status == "success":
            entry["success_count"] += 1
        entry["recognition_steps"] += count_recognition_steps(r.step_log)

    case_execution_stats = sorted(
        case_stats.values(),
        key=lambda x: (-x["run_count"], x["title"]),
    )

    return {
        "project_id": project_id,
        "metrics": {
            "total_task_runs": total_task_runs,
            "runs_last_30_days": runs_last_30_days,
            "success_runs": success_runs,
            "failed_runs": failed_runs,
            "cancelled_runs": cancelled_runs,
            "pending_or_running_runs": pending_running_runs,
            "total_recognition_steps": total_recognition_steps,
        },
        "case_execution_stats": case_execution_stats,
        "latest_report": latest_report,
        "active_robots": active_robots,
        "defect_trend": {
            "title": "未处理缺陷存量（每日结束时仍为未解决的缺陷数）",
            "days": 14,
            "labels": labels,
            "open_backlog_series": open_backlog,
            "note": "基于 defects 表；可与外部缺陷系统同步写入",
        },
    }
