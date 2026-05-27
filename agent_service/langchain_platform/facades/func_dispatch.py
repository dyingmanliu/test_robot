"""func_agent 调度 LangChain 门面。"""
from __future__ import annotations

from typing import Any, Callable

from agent_service.func_agent.core import FuncAgentDispatch
from agent_service.langchain_platform.graphs.func_dispatch import run_func_dispatch_graph


def run_func_agent_dispatch_langchain(
    dispatch: FuncAgentDispatch,
    *,
    on_autoglm_step: Callable[[int, Any], None] | None = None,
    on_midscene_line: Callable[[dict[str, Any]], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
    log_midscene_usage: Callable[[dict[str, Any]], None] | None = None,
):
    return run_func_dispatch_graph(
        dispatch,
        on_autoglm_step=on_autoglm_step,
        on_midscene_line=on_midscene_line,
        should_cancel=should_cancel,
        log_midscene_usage=log_midscene_usage,
    )
