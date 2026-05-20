from __future__ import annotations

import json
import os
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import logging

from dotenv import load_dotenv
from sqlalchemy.orm import Session

from func_agent.core import FuncAgentDispatch
from func_agent.orchestrator import run_func_agent_dispatch
from app.services.llm_usage_log import log_midscene_machine_line

log = logging.getLogger("app.executor")

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# run_id -> Event；在发起执行前注册，便于用户在 worker 启动前点击终止
_run_cancel_events: dict[int, threading.Event] = {}


def prepare_cancel_slot(run_id: int) -> None:
    if run_id not in _run_cancel_events:
        _run_cancel_events[run_id] = threading.Event()


def signal_cancel(run_id: int) -> bool:
    ev = _run_cancel_events.get(run_id)
    if ev is None:
        ev = threading.Event()
        ev.set()
        _run_cancel_events[run_id] = ev
        return True
    ev.set()
    return True


def execute_test_run(db: Session, run_id: int) -> None:
    from func_agent.backends.autoglm.agent import StepResult
    from app.models import RobotInstance, TestCase, TestRun

    cancel_ev = _run_cancel_events.setdefault(run_id, threading.Event())
    if cancel_ev.is_set():
        run = db.query(TestRun).filter(TestRun.id == run_id).first()
        if run is None:
            _run_cancel_events.pop(run_id, None)
            return
        run.status = "cancelled"
        run.output_message = "已在执行开始前终止"
        run.error_trace = None
        run.finished_at = datetime.utcnow()
        db.commit()
        _run_cancel_events.pop(run_id, None)
        return

    run = db.query(TestRun).filter(TestRun.id == run_id).first()
    if run is None:
        _run_cancel_events.pop(run_id, None)
        return
    case = db.query(TestCase).filter(TestCase.id == run.case_id).first()
    if case is None:
        run.status = "failed"
        run.error_trace = "测试用例不存在"
        run.finished_at = datetime.utcnow()
        db.commit()
        _run_cancel_events.pop(run_id, None)
        return

    inst: RobotInstance | None = None
    if run.robot_instance_id is not None:
        inst = db.query(RobotInstance).filter(RobotInstance.id == run.robot_instance_id).first()

    instance_lock = None
    lock_held = False
    if run.robot_instance_id is not None:
        from app.services.robot_run_guard import (
            busy_run_detail_message,
            find_active_run_for_instance,
            instance_execution_lock,
        )

        def _fail_busy(msg: str) -> None:
            run.status = "failed"
            run.output_message = msg
            run.error_trace = None
            run.finished_at = datetime.utcnow()
            db.commit()
            _run_cancel_events.pop(run_id, None)

        busy = find_active_run_for_instance(db, run.robot_instance_id, exclude_run_id=run_id)
        if busy is not None:
            _fail_busy(busy_run_detail_message(busy))
            return

        instance_lock = instance_execution_lock(run.robot_instance_id)
        if not instance_lock.acquire(blocking=False):
            busy = find_active_run_for_instance(db, run.robot_instance_id, exclude_run_id=run_id)
            _fail_busy(
                busy_run_detail_message(busy)
                if busy is not None
                else "该机器人实例已有任务在执行中，请稍后再试"
            )
            return
        lock_held = True

        busy = find_active_run_for_instance(db, run.robot_instance_id, exclude_run_id=run_id)
        if busy is not None:
            instance_lock.release()
            lock_held = False
            _fail_busy(busy_run_detail_message(busy))
            return

    backend = (getattr(inst, "test_agent_backend", None) or "autoglm").strip().lower()
    if backend not in ("autoglm", "midscene"):
        backend = "autoglm"

    from app.services.device_platform import (
        platform_label,
        resolve_execution_device_id,
        resolve_execution_platform,
        uses_midscene_runner,
    )

    platform = resolve_execution_platform(
        run_device_platform=getattr(run, "device_platform", None),
        instance_device_platform=getattr(inst, "device_platform", None) if inst else None,
        test_agent_backend=backend,
    )
    device_id = resolve_execution_device_id(
        run_device_id=getattr(run, "device_id", None),
        device_platform=platform,
    )
    use_midscene = uses_midscene_runner(
        test_agent_backend=backend,
        device_platform=platform,
    )

    case_format = (getattr(case, "case_format", None) or "structured").strip().lower()
    inst_code = getattr(inst, "instance_code", None) or "—"

    log.info(
        "开始执行 run_id=%s case_id=%s case=%r engine=%s platform=%s device_id=%s format=%s robot=%s",
        run_id,
        case.id,
        case.title,
        backend,
        platform,
        device_id or "(默认)",
        case_format,
        inst_code,
    )

    load_dotenv(_REPO_ROOT / ".env")

    if backend == "autoglm" and not (os.getenv("BIGMODEL_API_KEY") or os.getenv("ZHIPU_API_KEY")):
        run.status = "failed"
        run.output_message = (
            f"机器人 {inst_code} 使用 AutoGLM 引擎，需在 .env 配置 BIGMODEL_API_KEY 或 ZHIPU_API_KEY。"
        )
        run.error_trace = None
        run.finished_at = datetime.utcnow()
        db.commit()
        if lock_held and instance_lock is not None:
            instance_lock.release()
        _run_cancel_events.pop(run_id, None)
        return

    if use_midscene and backend == "midscene":
        base = (os.getenv("MIDSCENE_MODEL_BASE_URL") or "").lower()
        is_dashscope = "dashscope" in base
        api_key = (os.getenv("MIDSCENE_MODEL_API_KEY") or "").strip() or (
            (os.getenv("DASHSCOPE_API_KEY") or "").strip() if is_dashscope else ""
        ) or (
            (os.getenv("BIGMODEL_API_KEY") or os.getenv("ZHIPU_API_KEY") or "").strip()
            if not is_dashscope
            else ""
        )
        if not api_key:
            run.status = "failed"
            run.output_message = (
                "Midscene 引擎缺少模型 API Key：请在 .env 配置 MIDSCENE_MODEL_API_KEY 或 DASHSCOPE_API_KEY。"
            )
            run.error_trace = None
            run.finished_at = datetime.utcnow()
            db.commit()
            if lock_held and instance_lock is not None:
                instance_lock.release()
            _run_cancel_events.pop(run_id, None)
            return

    run.status = "running"
    run.started_at = datetime.utcnow()
    run.output_message = None
    run.error_trace = None
    run.report_path = None
    run.step_log = ""
    db.commit()

    def should_cancel() -> bool:
        return cancel_ev.is_set()

    def append_step_log(step_no: int, result: StepResult) -> None:
        row = db.query(TestRun).filter(TestRun.id == run_id).first()
        if row is None:
            return
        entry = {
            "step": step_no,
            "thinking": result.thinking,
            "action": result.action,
            "success": result.success,
            "finished": result.finished,
            "message": result.message,
        }
        line = json.dumps(entry, ensure_ascii=False, default=str) + "\n"
        row.step_log = (row.step_log or "") + line
        db.commit()

    def on_autoglm_step(step_no: int, result: StepResult) -> None:
        append_step_log(step_no, result)

    seq = {"n": 0}

    def midscene_obj_to_step(obj: dict[str, Any]) -> None:
        kind = obj.get("kind")
        if kind == "meta":
            append_step_log(
                0,
                StepResult(
                    success=True,
                    finished=False,
                    action={
                        "agent": "midscene",
                        "web_dispatch": {
                            "source": obj.get("source"),
                            "version": obj.get("version"),
                            "run_id": obj.get("run_id"),
                            "case_id": obj.get("case_id"),
                            "robot_instance_id": obj.get("robot_instance_id"),
                        },
                    },
                    thinking="",
                    message="已接收 Web 下发测试任务",
                ),
            )
            return
        if kind != "step":
            return
        raw_step = obj.get("step")
        try:
            sn = int(raw_step) if raw_step is not None else 0
        except (TypeError, ValueError):
            sn = 0
        if sn <= 0:
            seq["n"] += 1
            sn = seq["n"]
        phase = str(obj.get("phase") or "")
        task_txt = str(obj.get("task") or "")
        err = obj.get("error")
        success = phase != "error"
        action = {"agent": "midscene", "phase": phase, "task": task_txt}
        msg = str(err) if err else None
        append_step_log(
            sn,
            StepResult(
                success=success,
                finished=False,
                action=action,
                thinking="",
                message=msg,
            ),
        )

    from app.services.case_agent_text import build_agent_task_text, build_midscene_agent_steps

    preconditions = getattr(case, "preconditions", "") or ""
    steps_json = getattr(case, "steps_json", None) or "[]"
    agent_task = build_agent_task_text(
        task_text=case.task_text,
        preconditions=preconditions,
        steps_json=steps_json,
    )
    midscene_agent_steps = build_midscene_agent_steps(
        task_text=case.task_text,
        preconditions=preconditions,
        steps_json=steps_json,
    )

    dispatch_base: dict[str, Any] = {
        "version": 1,
        "run_id": run_id,
        "case_id": case.id,
        "robot_instance_id": run.robot_instance_id,
        "agent_backend": backend,
        "device_platform": platform,
        "device_id": device_id,
        "task_text": case.task_text,
        "preconditions": getattr(case, "preconditions", "") or "",
        "steps_json": getattr(case, "steps_json", None) or "[]",
    }

    try:
        web_dispatch: dict[str, Any] | None = None

        if case_format == "yaml" and backend != "midscene":
            row = db.query(TestRun).filter(TestRun.id == run_id).first()
            if row:
                row.status = "failed"
                row.output_message = (
                    "YAML 用例须使用 Midscene 执行引擎；请在机器人实例中将引擎设为 Midscene，"
                    f"设备平台可选 {platform_label(platform)}。"
                )
                row.error_trace = None
                row.finished_at = datetime.utcnow()
                db.commit()
            if lock_held and instance_lock is not None:
                instance_lock.release()
            _run_cancel_events.pop(run_id, None)
            return

        if use_midscene:
            if case_format == "yaml":
                from app.services.case_yaml import validate_case_yaml

                yaml_script = validate_case_yaml(getattr(case, "case_yaml", "") or "")
                web_dispatch = {
                    **dispatch_base,
                    "execution_mode": "yaml",
                    "yaml_script": yaml_script,
                    "case_format": "yaml",
                }
            else:
                web_dispatch = {
                    **dispatch_base,
                    "execution_mode": "natural",
                    "agent_task": agent_task,
                    "case_format": "structured",
                }
                if midscene_agent_steps:
                    web_dispatch["agent_steps"] = midscene_agent_steps
                    log.info(
                        "Midscene 拆步执行 run_id=%s steps=%s",
                        run_id,
                        len(midscene_agent_steps),
                    )
        elif backend == "autoglm":
            web_dispatch = None
        else:
            row = db.query(TestRun).filter(TestRun.id == run_id).first()
            if row:
                row.status = "failed"
                row.output_message = (
                    f"不支持的组合：引擎 {backend} + 设备 {platform_label(platform)}。"
                )
                row.error_trace = None
                row.finished_at = datetime.utcnow()
                db.commit()
            if lock_held and instance_lock is not None:
                instance_lock.release()
            _run_cancel_events.pop(run_id, None)
            return

        if use_midscene and web_dispatch is not None:
            from app.services.run_report import normalize_report_path

            ok, msg, report_file = run_func_agent_dispatch(
                FuncAgentDispatch(
                    backend=backend,
                    device_platform=platform,
                    device_id=device_id,
                    payload=web_dispatch,
                ),
                on_midscene_line=midscene_obj_to_step,
                should_cancel=should_cancel,
                log_midscene_usage=lambda obj: log_midscene_machine_line(obj, run_id=run_id),
            )
            row = db.query(TestRun).filter(TestRun.id == run_id).first()
            if row:
                row.report_path = normalize_report_path(report_file)
                if cancel_ev.is_set():
                    row.status = "cancelled"
                    row.output_message = msg or "用户已终止执行"
                elif ok:
                    row.status = "success"
                    row.output_message = msg
                else:
                    row.status = "failed"
                    row.output_message = msg
                    row.error_trace = None
        elif web_dispatch is None:
            outcome = run_func_agent_dispatch(
                FuncAgentDispatch(
                    backend=backend,
                    device_platform=platform,
                    device_id=device_id,
                    payload={"agent_task": agent_task},
                ),
                on_autoglm_step=on_autoglm_step,
                should_cancel=should_cancel,
            )
            row = db.query(TestRun).filter(TestRun.id == run_id).first()
            if row:
                if cancel_ev.is_set():
                    row.status = "cancelled"
                    row.output_message = outcome.message or "用户已终止执行"
                elif outcome.ok:
                    row.status = "success"
                    row.output_message = outcome.message
                else:
                    row.status = "failed"
                    row.output_message = outcome.message
                    row.error_trace = None
    except Exception:
        log.exception("执行异常 run_id=%s case_id=%s", run_id, case.id)
        row = db.query(TestRun).filter(TestRun.id == run_id).first()
        if row:
            row.status = "failed"
            row.error_trace = traceback.format_exc()
    finally:
        row = db.query(TestRun).filter(TestRun.id == run_id).first()
        if row:
            row.finished_at = datetime.utcnow()
            db.commit()
            log.info(
                "执行结束 run_id=%s status=%s message=%s",
                run_id,
                row.status,
                (row.output_message or "")[:200],
            )
        if lock_held and instance_lock is not None:
            instance_lock.release()
        _run_cancel_events.pop(run_id, None)
