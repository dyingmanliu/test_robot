from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv
from sqlalchemy.orm import Session

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


def run_phone_agent_task(
    task: str,
    *,
    on_step: Callable[[int, Any], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
):
    """Runs PhoneTestAgent in-process (blocking). Loads API keys from repo-root .env."""
    load_dotenv(_REPO_ROOT / ".env")
    os.chdir(_REPO_ROOT)

    from autoglm_phone_agent.agent import AgentConfig, PhoneTestAgent
    from autoglm_phone_agent.model.client import ModelConfig

    api_key = os.getenv("BIGMODEL_API_KEY") or os.getenv("ZHIPU_API_KEY")
    if not api_key:
        raise RuntimeError("请配置 BIGMODEL_API_KEY 或 ZHIPU_API_KEY（环境变量或项目根目录 .env）")

    model_config = ModelConfig(
        base_url=os.getenv("OPENAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
        api_key=api_key,
        model_name=os.getenv("PHONE_AGENT_MODEL", "autoglm-phone"),
    )
    agent_config = AgentConfig(
        max_steps=int(os.getenv("PHONE_AGENT_MAX_STEPS", "100")),
        device_id=os.getenv("ADB_DEVICE_ID") or None,
        verbose=False,
    )
    agent = PhoneTestAgent(
        model_config=model_config,
        agent_config=agent_config,
        print_model_stream=False,
    )
    return agent.run(task.strip(), on_step=on_step, should_cancel=should_cancel)


def run_midscene_agent_task(
    dispatch: dict[str, Any],
    *,
    on_machine_line: Callable[[dict[str, Any]], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> tuple[bool, str]:
    """通过子进程运行 midscene_agent CLI（--web-dispatch：stdin 为 Web 下发 JSON）。"""
    load_dotenv(_REPO_ROOT / ".env")
    mid_root = _REPO_ROOT / "midscene_agent"
    cli_rel = Path("src/cli.ts")
    if not (mid_root / cli_rel).is_file():
        raise RuntimeError(f"未找到 Midscene CLI：{mid_root / cli_rel}")

    local_tsx = mid_root / "node_modules" / ".bin" / "tsx"
    if local_tsx.is_file():
        cmd = [str(local_tsx), str(cli_rel), "--web-dispatch"]
    elif (tsx_which := shutil.which("tsx")):
        cmd = [tsx_which, str(mid_root / cli_rel), "--web-dispatch"]
    else:
        npx = os.getenv("TCM_NPX_BIN", "npx")
        cmd = [npx, "--yes", "tsx", str(cli_rel), "--web-dispatch"]

    env = {**os.environ}
    env.setdefault("FORCE_COLOR", "0")
    proc = subprocess.Popen(
        cmd,
        cwd=str(mid_root),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )
    assert proc.stdin is not None and proc.stdout is not None

    stdin_payload = json.dumps(dispatch, ensure_ascii=False, default=str) + "\n"

    def write_stdin() -> None:
        try:
            proc.stdin.write(stdin_payload)
            proc.stdin.close()
        except BrokenPipeError:
            pass

    threading.Thread(target=write_stdin, daemon=True).start()

    line_q: queue.Queue[str | None] = queue.Queue()

    def reader() -> None:
        try:
            for raw in iter(proc.stdout.readline, ""):
                line_q.put(raw)
        finally:
            line_q.put(None)

    threading.Thread(target=reader, daemon=True).start()

    final_ok: bool | None = None
    final_message = ""

    def process_line(raw: str) -> None:
        nonlocal final_ok, final_message
        line = raw.strip()
        if not line:
            return
        try:
            obj: dict[str, Any] = json.loads(line)
        except json.JSONDecodeError:
            return
        if on_machine_line:
            on_machine_line(obj)
        if obj.get("kind") == "done":
            final_ok = bool(obj.get("ok"))
            final_message = str(obj.get("message") or "")

    while True:
        if should_cancel and should_cancel():
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
            return False, "执行已取消"

        try:
            raw = line_q.get(timeout=0.35)
        except queue.Empty:
            if proc.poll() is not None:
                while True:
                    try:
                        r = line_q.get_nowait()
                    except queue.Empty:
                        break
                    if r is None:
                        break
                    process_line(r)
                break
            continue

        if raw is None:
            break
        process_line(raw)

    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)

    if final_ok is not None:
        return final_ok, final_message

    code = proc.returncode if proc.returncode is not None else -1
    return False, f"Midscene 子进程异常结束（exit {code}），未收到结果行"


def execute_test_run(db: Session, run_id: int) -> None:
    from autoglm_phone_agent.agent import StepResult
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
    backend = (getattr(inst, "test_agent_backend", None) or "autoglm").strip().lower()
    if backend not in ("autoglm", "midscene"):
        backend = "autoglm"

    run.status = "running"
    run.started_at = datetime.utcnow()
    run.output_message = None
    run.error_trace = None
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

    from app.services.case_agent_text import build_agent_task_text

    case_format = (getattr(case, "case_format", None) or "structured").strip().lower()
    agent_task = build_agent_task_text(
        task_text=case.task_text,
        preconditions=getattr(case, "preconditions", "") or "",
        steps_json=getattr(case, "steps_json", None) or "[]",
    )

    try:
        if backend == "midscene":
            if case_format == "yaml":
                from app.services.case_yaml import validate_case_yaml

                yaml_script = validate_case_yaml(getattr(case, "case_yaml", "") or "")
                web_dispatch = {
                    "version": 1,
                    "run_id": run_id,
                    "case_id": case.id,
                    "robot_instance_id": run.robot_instance_id,
                    "execution_mode": "yaml",
                    "yaml_script": yaml_script,
                    "case_format": "yaml",
                    "task_text": case.task_text,
                    "preconditions": getattr(case, "preconditions", "") or "",
                    "steps_json": getattr(case, "steps_json", None) or "[]",
                }
            else:
                web_dispatch = {
                    "version": 1,
                    "run_id": run_id,
                    "case_id": case.id,
                    "robot_instance_id": run.robot_instance_id,
                    "execution_mode": "natural",
                    "agent_task": agent_task,
                    "case_format": "structured",
                    "task_text": case.task_text,
                    "preconditions": getattr(case, "preconditions", "") or "",
                    "steps_json": getattr(case, "steps_json", None) or "[]",
                }
        elif case_format == "yaml":
            row = db.query(TestRun).filter(TestRun.id == run_id).first()
            if row:
                row.status = "failed"
                row.output_message = "YAML 用例须绑定 Midscene 机器人实例执行"
                row.error_trace = None
                row.finished_at = datetime.utcnow()
                db.commit()
            _run_cancel_events.pop(run_id, None)
            return
        else:
            web_dispatch = None

        if backend == "midscene":
            ok, msg = run_midscene_agent_task(
                web_dispatch,
                on_machine_line=midscene_obj_to_step,
                should_cancel=should_cancel,
            )
            row = db.query(TestRun).filter(TestRun.id == run_id).first()
            if row:
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
            outcome = run_phone_agent_task(agent_task, on_step=on_autoglm_step, should_cancel=should_cancel)
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
        row = db.query(TestRun).filter(TestRun.id == run_id).first()
        if row:
            row.status = "failed"
            row.error_trace = traceback.format_exc()
    finally:
        row = db.query(TestRun).filter(TestRun.id == run_id).first()
        if row:
            row.finished_at = datetime.utcnow()
            db.commit()
        _run_cancel_events.pop(run_id, None)
