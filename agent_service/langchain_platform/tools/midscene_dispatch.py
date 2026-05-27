"""Midscene 子进程调度 Tool 封装。"""

from __future__ import annotations

from typing import Any, Callable

from agent_service.analysis_agent.feature_explore.types import CancelCheck, ExploreDispatch
from agent_service.func_agent.backends.midscene.runtime import run_midscene_task


def run_midscene_explore_dispatch(
    dispatch: ExploreDispatch,
    *,
    on_machine_line: Callable[[dict[str, Any]], None] | None = None,
    should_cancel: CancelCheck | None = None,
    log_model_usage: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[bool, str, str | None]:
    return run_midscene_task(
        dispatch.to_midscene_payload(),
        on_machine_line=on_machine_line,
        should_cancel=should_cancel,
        log_model_usage=log_model_usage,
    )


def run_midscene_web_dispatch(
    payload: dict[str, Any],
    *,
    on_machine_line: Callable[[dict[str, Any]], None] | None = None,
    should_cancel: CancelCheck | None = None,
    log_model_usage: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[bool, str, str | None]:
    return run_midscene_task(
        payload,
        on_machine_line=on_machine_line,
        should_cancel=should_cancel,
        log_model_usage=log_model_usage,
    )
