"""Midscene 执行 LangGraph 薄适配。"""
from __future__ import annotations

from typing import Any, Callable, TypedDict

from langgraph.graph import END, StateGraph

from agent_service.langchain_platform.tools.midscene_dispatch import run_midscene_web_dispatch


class MidsceneState(TypedDict, total=False):
    payload: dict[str, Any]
    on_machine_line: Callable[[dict[str, Any]], None] | None
    should_cancel: Callable[[], bool] | None
    log_model_usage: Callable[[dict[str, Any]], None] | None
    ok: bool
    message: str
    report_file: str | None


def _stream_subprocess(state: MidsceneState) -> dict[str, Any]:
    ok, msg, report_file = run_midscene_web_dispatch(
        state["payload"],
        on_machine_line=state.get("on_machine_line"),
        should_cancel=state.get("should_cancel"),
        log_model_usage=state.get("log_model_usage"),
    )
    return {"ok": ok, "message": msg, "report_file": report_file}


def build_midscene_exec_graph():
    g = StateGraph(MidsceneState)
    g.add_node("stream_subprocess", _stream_subprocess)
    g.set_entry_point("stream_subprocess")
    g.add_edge("stream_subprocess", END)
    return g.compile()


def run_midscene_graph(
    payload: dict[str, Any],
    *,
    on_machine_line: Callable[[dict[str, Any]], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
    log_model_usage: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[bool, str, str | None]:
    graph = build_midscene_exec_graph()
    final = graph.invoke(
        {
            "payload": payload,
            "on_machine_line": on_machine_line,
            "should_cancel": should_cancel,
            "log_model_usage": log_model_usage,
        }
    )
    return bool(final.get("ok")), str(final.get("message") or ""), final.get("report_file")
