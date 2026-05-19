"""APP 功能遍历任务：子进程 Midscene explore + Excel 导出。"""

from __future__ import annotations

import json
import os
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy.orm import Session

from app.executor import run_midscene_agent_task
from app.services.llm_usage_log import log_midscene_machine_line
from app.models import AppExploreRun, RobotInstance
from app.services.app_explore_export import write_explore_excel

_REPO_ROOT = Path(__file__).resolve().parents[4]
_EXPORT_DIR = _REPO_ROOT / "web" / "backend" / "data" / "explore_exports"

_explore_cancel_events: dict[int, threading.Event] = {}


def prepare_explore_cancel_slot(run_id: int) -> None:
    if run_id not in _explore_cancel_events:
        _explore_cancel_events[run_id] = threading.Event()


def signal_explore_cancel(run_id: int) -> bool:
    ev = _explore_cancel_events.get(run_id)
    if ev is None:
        ev = threading.Event()
        ev.set()
        _explore_cancel_events[run_id] = ev
        return True
    ev.set()
    return True


def find_active_explore_for_instance(
    db: Session,
    robot_instance_id: int,
    *,
    exclude_run_id: int | None = None,
) -> AppExploreRun | None:
    q = db.query(AppExploreRun).filter(
        AppExploreRun.robot_instance_id == robot_instance_id,
        AppExploreRun.status.in_(("pending", "running")),
    )
    if exclude_run_id is not None:
        q = q.filter(AppExploreRun.id != exclude_run_id)
    return q.order_by(AppExploreRun.id.asc()).first()


def explore_busy_message(busy: AppExploreRun) -> str:
    label = "排队中" if busy.status == "pending" else "执行中"
    return (
        f"该机器人实例已有功能探索任务{label}（探索 ID {busy.id}），"
        f"请等待其完成或取消后再发起"
    )


def execute_app_explore_run(db: Session, run_id: int) -> None:
    load_dotenv(_REPO_ROOT / ".env")
    cancel_ev = _explore_cancel_events.setdefault(run_id, threading.Event())

    run = db.query(AppExploreRun).filter(AppExploreRun.id == run_id).first()
    if run is None:
        _explore_cancel_events.pop(run_id, None)
        return

    if cancel_ev.is_set():
        run.status = "cancelled"
        run.output_message = "已在执行开始前取消"
        run.finished_at = datetime.utcnow()
        db.commit()
        _explore_cancel_events.pop(run_id, None)
        return

    inst = db.query(RobotInstance).filter(RobotInstance.id == run.robot_instance_id).first()
    if inst is None:
        run.status = "failed"
        run.output_message = "机器人实例不存在"
        run.finished_at = datetime.utcnow()
        db.commit()
        _explore_cancel_events.pop(run_id, None)
        return

    backend = (inst.test_agent_backend or "autoglm").strip().lower()
    if backend != "midscene":
        run.status = "failed"
        run.output_message = "功能探索仅支持 test_agent_backend=midscene 的机器人实例"
        run.finished_at = datetime.utcnow()
        db.commit()
        _explore_cancel_events.pop(run_id, None)
        return

    run.status = "running"
    run.started_at = datetime.utcnow()
    run.output_message = None
    run.error_trace = None
    run.step_log = ""
    db.commit()

    tree_holder: dict[str, Any] = {"tree": None}

    def append_log(obj: dict[str, Any]) -> None:
        row = db.query(AppExploreRun).filter(AppExploreRun.id == run_id).first()
        if row is None:
            return
        line = json.dumps(obj, ensure_ascii=False, default=str) + "\n"
        row.step_log = (row.step_log or "") + line

        kind = obj.get("kind")
        if kind == "explore_feature":
            feat = obj.get("feature")
            if isinstance(feat, dict):
                row.feature_count = int(row.feature_count or 0) + 0
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
            row = db.query(AppExploreRun).filter(AppExploreRun.id == run_id).first()
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
        elif obj.get("kind") == "explore_page":
            pass

    dispatch = {
        "version": 1,
        "execution_mode": "explore",
        "run_id": run_id,
        "robot_instance_id": run.robot_instance_id,
        "app_name": run.app_name,
        "bundle_id": run.bundle_id,
        "max_screens": run.max_screens,
        "max_depth": run.max_depth,
    }

    try:
        ok, msg, report_file = run_midscene_agent_task(
            dispatch,
            on_machine_line=on_machine_line,
            should_cancel=cancel_ev.is_set,
            log_run_id=run_id,
        )
    except Exception:
        row = db.query(AppExploreRun).filter(AppExploreRun.id == run_id).first()
        if row:
            row.status = "failed"
            row.error_trace = traceback.format_exc()
            row.output_message = "探索执行异常"
            row.finished_at = datetime.utcnow()
            db.commit()
        _explore_cancel_events.pop(run_id, None)
        return

    row = db.query(AppExploreRun).filter(AppExploreRun.id == run_id).first()
    if row is None:
        _explore_cancel_events.pop(run_id, None)
        return

    if cancel_ev.is_set():
        row.status = "cancelled"
        row.output_message = "探索已取消"
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
            "app_name": row.app_name,
            "bundle_id": row.bundle_id or "",
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
        excel_name = f"app-explore-{run_id}.xlsx"
        excel_abs = _EXPORT_DIR / excel_name
        write_explore_excel(
            tree,
            excel_abs,
            device_id=os.getenv("HDC_DEVICE_ID") or "",
            model_name=os.getenv("MIDSCENE_MODEL_NAME") or "",
        )
        row.excel_path = str(excel_abs)
    except Exception as ex:
        if row.status == "success":
            row.status = "failed"
        row.output_message = (row.output_message or "") + f"；Excel 导出失败: {ex}"

    row.finished_at = datetime.utcnow()
    db.commit()
    _explore_cancel_events.pop(run_id, None)
