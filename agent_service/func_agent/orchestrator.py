from __future__ import annotations

from typing import Any, Callable

from agent_service.func_agent.backends import run_autoglm_task, run_midscene_task
from agent_service.func_agent.core import FuncAgentDispatch


def run_func_agent_dispatch(
    dispatch: FuncAgentDispatch,
    *,
    on_autoglm_step: Callable[[int, Any], None] | None = None,
    on_midscene_line: Callable[[dict[str, Any]], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
    log_midscene_usage: Callable[[dict[str, Any]], None] | None = None,
):
    backend = (dispatch.backend or "autoglm").strip().lower()
    if backend == "midscene":
        return run_midscene_task(
            dispatch.payload,
            on_machine_line=on_midscene_line,
            should_cancel=should_cancel,
            log_model_usage=log_midscene_usage,
        )
    if backend == "autoglm":
        task = str(dispatch.payload.get("agent_task") or "").strip()
        return run_autoglm_task(
            task,
            device_platform=dispatch.device_platform,
            device_id=dispatch.device_id,
            on_step=on_autoglm_step,
            should_cancel=should_cancel,
        )
    raise ValueError(f"Unsupported agent_service/func_agent backend: {backend}")
