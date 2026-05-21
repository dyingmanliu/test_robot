"""项目功能点分析：测试分析实例 + Midscene explore 子进程。"""

from __future__ import annotations

import json
import os
import sys
import threading
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

from agent_service.func_agent.backends.midscene.runtime import run_midscene_task
from app.models import ProjectFeatureAnalysisRun, RobotInstance
from app.services.app_explore_export import write_explore_excel
from app.services.device_platform import resolve_execution_device_id, resolve_execution_platform
from app.services.llm_usage_log import log_midscene_machine_line

_feature_cancel_events: dict[int, threading.Event] = {}


def prepare_feature_cancel_slot(run_id: int) -> None:
    if run_id not in _feature_cancel_events:
        _feature_cancel_events[run_id] = threading.Event()


def signal_feature_cancel(run_id: int) -> bool:
    ev = _feature_cancel_events.get(run_id)
    if ev is None:
        ev = threading.Event()
        ev.set()
        _feature_cancel_events[run_id] = ev
        return True
    ev.set()
    return True


def execute_feature_analysis_run(db: Session, run_id: int) -> None:
    load_dotenv(_REPO_ROOT / ".env")
    cancel_ev = _feature_cancel_events.setdefault(run_id, threading.Event())

    run = db.query(ProjectFeatureAnalysisRun).filter(ProjectFeatureAnalysisRun.id == run_id).first()
    if run is None:
        _feature_cancel_events.pop(run_id, None)
        return

    if cancel_ev.is_set():
        run.status = "cancelled"
        run.output_message = "已在执行开始前取消"
        run.finished_at = datetime.utcnow()
        db.commit()
        _feature_cancel_events.pop(run_id, None)
        return

    inst = db.query(RobotInstance).filter(RobotInstance.id == run.robot_instance_id).first()
    if inst is None:
        run.status = "failed"
        run.output_message = "机器人实例不存在"
        run.finished_at = datetime.utcnow()
        db.commit()
        _feature_cancel_events.pop(run_id, None)
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
                try:
                    existing = json.loads(row.feature_json or "{}")
                except json.JSONDecodeError:
                    existing = {"features": []}
                feats = existing.get("features")
                if not isinstance(feats, list):
                    feats = []
                feat = obj.get("feature")
                if isinstance(feat, dict):
                    feats.append(feat)
                    existing["features"] = feats
                    row.feature_json = json.dumps(existing, ensure_ascii=False)
                    row.feature_count = len(feats)
                    db.commit()

    bundle_id = (run.bundle_id or "").strip()
    app_name = (run.app_display_name or bundle_id).strip()

    dispatch = {
        "version": 1,
        "execution_mode": "explore",
        "run_id": run_id,
        "robot_instance_id": run.robot_instance_id,
        "agent_backend": "midscene",
        "device_platform": platform,
        "device_id": device_id or "",
        "app_name": app_name,
        "bundle_id": bundle_id,
        "max_screens": run.max_screens,
        "max_depth": run.max_depth,
    }

    try:
        ok, msg, report_file = run_midscene_task(
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
            db.commit()
        _feature_cancel_events.pop(run_id, None)
        return

    row = db.query(ProjectFeatureAnalysisRun).filter(ProjectFeatureAnalysisRun.id == run_id).first()
    if row is None:
        _feature_cancel_events.pop(run_id, None)
        return

    if cancel_ev.is_set():
        row.status = "cancelled"
        row.output_message = "分析已取消"
    elif ok:
        row.status = "success"
        row.output_message = msg
    else:
        row.status = "failed" if not (tree_holder.get("tree") or row.feature_json) else "success"
        row.output_message = msg

    tree = tree_holder.get("tree")
    if tree is None and row.feature_json:
        try:
            tree = json.loads(row.feature_json)
        except json.JSONDecodeError:
            tree = None

    if tree is None:
        tree = {
            "app_name": app_name,
            "bundle_id": bundle_id,
            "started_at": (row.started_at or row.created_at).isoformat()
            if row.started_at or row.created_at
            else "",
            "finished_at": datetime.utcnow().isoformat(),
            "features": [],
            "screens_visited": row.screens_visited or 0,
        }

    row.feature_json = json.dumps(tree, ensure_ascii=False)
    row.feature_count = len(tree.get("features") or [])
    row.screens_visited = int(tree.get("screens_visited") or row.screens_visited or 0)
    resolved_bundle = str(tree.get("bundle_id") or "").strip()
    if resolved_bundle:
        row.bundle_id = resolved_bundle

    if report_file:
        row.report_path = report_file

    try:
        _EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        excel_name = f"feature-analysis-{run.project_id}-{run_id}.xlsx"
        excel_abs = _EXPORT_DIR / excel_name
        write_explore_excel(
            tree,
            excel_abs,
            device_id=device_id or "",
            model_name=os.getenv("MIDSCENE_MODEL_NAME") or "",
        )
        row.excel_path = str(excel_abs)
    except Exception as ex:
        if row.status == "success":
            row.status = "failed"
        row.output_message = (row.output_message or "") + f"；Excel 导出失败: {ex}"

    row.finished_at = datetime.utcnow()
    db.commit()
    _feature_cancel_events.pop(run_id, None)
