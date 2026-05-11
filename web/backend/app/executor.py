from __future__ import annotations

import json
import os
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


def execute_test_run(db: Session, run_id: int) -> None:
    from app.models import TestCase, TestRun

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

    run.status = "running"
    run.started_at = datetime.utcnow()
    run.output_message = None
    run.error_trace = None
    run.step_log = ""
    db.commit()

    from autoglm_phone_agent.agent import StepResult

    def should_cancel() -> bool:
        return cancel_ev.is_set()

    def on_step(step_no: int, result: StepResult) -> None:
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

    from app.services.case_agent_text import build_agent_task_text

    agent_task = build_agent_task_text(
        task_text=case.task_text,
        preconditions=getattr(case, "preconditions", "") or "",
        steps_json=getattr(case, "steps_json", None) or "[]",
    )

    try:
        outcome = run_phone_agent_task(agent_task, on_step=on_step, should_cancel=should_cancel)
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
