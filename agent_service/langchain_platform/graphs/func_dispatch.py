"""统一功能测试调度 LangGraph。"""
from __future__ import annotations

from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from agent_service.func_agent.core import FuncAgentDispatch
from agent_service.langchain_platform.graphs.autoglm_exec import run_autoglm_graph
from agent_service.langchain_platform.graphs.midscene_exec import run_midscene_graph


class FuncDispatchState(TypedDict, total=False):
    dispatch: FuncAgentDispatch
    on_autoglm_step: Callable[[int, Any], None] | None
    on_midscene_line: Callable[[dict[str, Any]], None] | None
    should_cancel: Callable[[], bool] | None
    log_midscene_usage: Callable[[dict[str, Any]], None] | None
    result: Any


def _route_backend(state: FuncDispatchState) -> str:
    backend = (state["dispatch"].backend or "autoglm").strip().lower()
    if backend == "midscene":
        return "midscene"
    if backend == "autoglm":
        return "autoglm"
    return "unsupported"


def _run_autoglm(state: FuncDispatchState) -> dict[str, Any]:
    dispatch = state["dispatch"]
    task = str(dispatch.payload.get("agent_task") or "").strip()
    outcome = run_autoglm_graph(
        task,
        device_platform=dispatch.device_platform,
        device_id=dispatch.device_id,
        on_step=state.get("on_autoglm_step"),
        should_cancel=state.get("should_cancel"),
    )
    return {"result": outcome}


def _run_midscene(state: FuncDispatchState) -> dict[str, Any]:
    dispatch = state["dispatch"]
    result = run_midscene_graph(
        dispatch.payload,
        on_machine_line=state.get("on_midscene_line"),
        should_cancel=state.get("should_cancel"),
        log_model_usage=state.get("log_midscene_usage"),
    )
    return {"result": result}


def _unsupported(state: FuncDispatchState) -> dict[str, Any]:
    backend = state["dispatch"].backend
    raise ValueError(f"Unsupported agent_service/func_agent backend: {backend}")


def build_func_dispatch_graph():
    g = StateGraph(FuncDispatchState)
    g.add_node("run_autoglm", _run_autoglm)
    g.add_node("run_midscene", _run_midscene)
    g.add_node("unsupported", _unsupported)
    g.add_conditional_edges(
        START,
        _route_backend,
        {"autoglm": "run_autoglm", "midscene": "run_midscene", "unsupported": "unsupported"},
    )
    g.add_edge("run_autoglm", END)
    g.add_edge("run_midscene", END)
    g.add_edge("unsupported", END)
    return g.compile()


def run_func_dispatch_graph(
    dispatch: FuncAgentDispatch,
    *,
    on_autoglm_step: Callable[[int, Any], None] | None = None,
    on_midscene_line: Callable[[dict[str, Any]], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
    log_midscene_usage: Callable[[dict[str, Any]], None] | None = None,
):
    graph = build_func_dispatch_graph()
    final = graph.invoke(
        {
            "dispatch": dispatch,
            "on_autoglm_step": on_autoglm_step,
            "on_midscene_line": on_midscene_line,
            "should_cancel": should_cancel,
            "log_midscene_usage": log_midscene_usage,
        }
    )
    return final["result"]
