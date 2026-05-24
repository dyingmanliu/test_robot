"""Web 适配层：ORM + DB 持久化 → FeatureExploreAgent（对齐 case_generation → AnalysisAgent）。"""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy.orm import Session

_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_EXPORT_DIR = _REPO_ROOT / "web" / "backend" / "data" / "feature_analysis_exports"

from agent_service.analysis_agent.feature_explore import ExploreDispatch, FeatureExploreAgent
from app.models import ProjectFeatureAnalysisRun, RobotInstance
from app.services.app_explore_export import write_explore_excel
from app.services.device_platform import resolve_execution_device_id, resolve_execution_platform
from app.services.feature_analysis_service import get_feature_cancel_event
from app.services.llm_usage_log import log_midscene_machine_line


def _persist_finalized_tree(
    row: ProjectFeatureAnalysisRun,
    *,
    tree: dict[str, Any] | None,
    app_name: str,
    bundle_id: str,
) -> dict[str, Any]:
    from agent_service.analysis_agent.feature_explore.tree_build import ensure_giic_tree

    finalized = FeatureExploreAgent.finalize_tree(
        tree=tree,
        feature_json=row.feature_json,
        app_name=app_name,
        bundle_id=bundle_id,
        started_at=row.started_at or row.created_at,
        screens_visited=row.screens_visited or 0,
    )
    finalized = ensure_giic_tree(finalized)
    row.feature_json = json.dumps(finalized, ensure_ascii=False)
    row.feature_count = len(finalized.get("features") or [])
    row.screens_visited = int(finalized.get("screens_visited") or row.screens_visited or 0)
    resolved_bundle = str(finalized.get("bundle_id") or "").strip()
    if resolved_bundle:
        row.bundle_id = resolved_bundle
    return finalized


def _try_write_explore_excel(
    tree: dict[str, Any],
    *,
    project_id: int,
    run_id: int,
    device_id: str,
) -> Path | None:
    _EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    excel_name = f"feature-analysis-{project_id}-{run_id}.xlsx"
    excel_abs = _EXPORT_DIR / excel_name
    write_explore_excel(
        tree,
        excel_abs,
        device_id=device_id or "",
        model_name=os.getenv("MIDSCENE_MODEL_NAME") or "",
    )
    return excel_abs


def execute_feature_analysis_run(db: Session, run_id: int) -> None:
    load_dotenv(_REPO_ROOT / ".env")
    cancel_ev = get_feature_cancel_event(run_id)

    run = db.query(ProjectFeatureAnalysisRun).filter(ProjectFeatureAnalysisRun.id == run_id).first()
    if run is None:
        from app.services.feature_analysis_service import clear_feature_cancel_slot

        clear_feature_cancel_slot(run_id)
        return

    if cancel_ev.is_set():
        run.status = "cancelled"
        run.output_message = "已在执行开始前取消"
        run.finished_at = datetime.utcnow()
        db.commit()
        _clear_slot(run_id)
        return

    inst = db.query(RobotInstance).filter(RobotInstance.id == run.robot_instance_id).first()
    if inst is None:
        run.status = "failed"
        run.output_message = "机器人实例不存在"
        run.finished_at = datetime.utcnow()
        db.commit()
        _clear_slot(run_id)
        return

    platform = resolve_execution_platform(
        run_device_platform=run.device_platform,
        instance_device_platform=inst.device_platform,
        test_agent_backend="midscene",
    )
    device_id = resolve_execution_device_id(
        run_device_id=run.device_id,
        device_platform=platform,
    )

    run.status = "running"
    run.started_at = datetime.utcnow()
    run.output_message = None
    run.error_trace = None
    run.step_log = ""
    db.commit()

    tree_holder: dict[str, Any] = {"tree": None}
    agent = FeatureExploreAgent(repo_root=_REPO_ROOT)

    def append_log(obj: dict[str, Any]) -> None:
        row = db.query(ProjectFeatureAnalysisRun).filter(ProjectFeatureAnalysisRun.id == run_id).first()
        if row is None:
            return
        line = json.dumps(obj, ensure_ascii=False, default=str) + "\n"
        row.step_log = (row.step_log or "") + line
        kind = obj.get("kind")
        if kind == "done" and isinstance(obj.get("tree"), dict):
            tree_holder["tree"] = obj["tree"]
            row.feature_count = len(obj["tree"].get("features") or [])
            row.screens_visited = int(
                obj["tree"].get("screens_visited") or row.screens_visited or 0
            )
        db.commit()

    def on_machine_line(obj: dict[str, Any]) -> None:
        if obj.get("kind") == "model_usage":
            log_midscene_machine_line(obj, run_id=run_id)
        append_log(obj)
        if obj.get("kind") == "explore_feature":
            row = db.query(ProjectFeatureAnalysisRun).filter(ProjectFeatureAnalysisRun.id == run_id).first()
            if row:
                row.feature_json, row.feature_count = FeatureExploreAgent.merge_feature_from_line(
                    row.feature_json, obj
                )
                db.commit()

    bundle_id = (run.bundle_id or "").strip()
    app_name = (run.app_display_name or bundle_id).strip()

    dispatch = ExploreDispatch(
        device_platform=platform,
        device_id=device_id or "",
        app_name=app_name,
        bundle_id=bundle_id,
        max_screens=run.max_screens,
        max_depth=run.max_depth,
        traverse_mode=(run.traverse_mode or "hybrid").strip() or "hybrid",
        bfs_max_depth=int(run.bfs_max_depth or 1),
        fair_share_per_root=int(run.fair_share_per_root or 0),
        run_id=run_id,
        robot_instance_id=run.robot_instance_id,
    )

    try:
        result = agent.run(
            dispatch,
            on_machine_line=on_machine_line,
            should_cancel=cancel_ev.is_set,
            log_model_usage=lambda obj: log_midscene_machine_line(obj, run_id=run_id),
        )
    except Exception:
        row = db.query(ProjectFeatureAnalysisRun).filter(ProjectFeatureAnalysisRun.id == run_id).first()
        if row:
            row.status = "failed"
            row.error_trace = traceback.format_exc()
            row.output_message = "功能点分析执行异常"
            row.finished_at = datetime.utcnow()
            if row.feature_json or tree_holder.get("tree"):
                try:
                    finalized = _persist_finalized_tree(
                        row,
                        tree=tree_holder.get("tree"),
                        app_name=app_name,
                        bundle_id=bundle_id,
                    )
                    row.output_message = (
                        "功能点分析执行异常（已保留部分采集结果，可确认保存功能树）"
                    )
                    try:
                        excel_abs = _try_write_explore_excel(
                            finalized,
                            project_id=row.project_id,
                            run_id=run_id,
                            device_id=device_id or "",
                        )
                        row.excel_path = str(excel_abs)
                    except Exception as ex:
                        row.output_message += f"；Excel 导出失败: {ex}"
                except Exception:
                    pass
            db.commit()
        _clear_slot(run_id)
        return

    row = db.query(ProjectFeatureAnalysisRun).filter(ProjectFeatureAnalysisRun.id == run_id).first()
    if row is None:
        _clear_slot(run_id)
        return

    ok = result.ok
    msg = result.message
    tree = result.tree or tree_holder.get("tree")

    if cancel_ev.is_set():
        row.status = "cancelled"
        row.output_message = "分析已取消（可确认保存已采集的功能树）"
    elif ok:
        row.status = "success"
        row.output_message = msg
    else:
        row.status = "failed" if not (tree or row.feature_json) else "success"
        row.output_message = msg

    tree = _persist_finalized_tree(
        row, tree=tree, app_name=app_name, bundle_id=bundle_id
    )

    if result.report_file:
        row.report_path = result.report_file

    try:
        excel_abs = _try_write_explore_excel(
            tree,
            project_id=run.project_id,
            run_id=run_id,
            device_id=device_id or "",
        )
        row.excel_path = str(excel_abs)
    except Exception as ex:
        if row.status == "success":
            row.status = "failed"
        row.output_message = (row.output_message or "") + f"；Excel 导出失败: {ex}"

    row.finished_at = datetime.utcnow()
    db.commit()
    _clear_slot(run_id)


def _clear_slot(run_id: int) -> None:
    from app.services.feature_analysis_service import clear_feature_cancel_slot

    clear_feature_cancel_slot(run_id)
