"""统一功能测试调度 LangGraph（含 Agentic RAG prefetch）。"""
from __future__ import annotations

from typing import Any, Callable, TypedDict

from langgraph.graph import END, StateGraph

from agent_service.func_agent.core import FuncAgentDispatch
from agent_service.langchain_platform.graphs.autoglm_exec import run_autoglm_graph
from agent_service.langchain_platform.graphs.midscene_exec import run_midscene_graph
from agent_service.langchain_platform.tools.knowledge_query import (
    KnowledgeToolContext,
    fetch_agent_context,
    query_knowledge_http,
)


class FuncDispatchState(TypedDict, total=False):
    dispatch: FuncAgentDispatch
    on_autoglm_step: Callable[[int, Any], None] | None
    on_midscene_line: Callable[[dict[str, Any]], None] | None
    should_cancel: Callable[[], bool] | None
    log_midscene_usage: Callable[[dict[str, Any]], None] | None
    result: Any
    rag_trace: list[dict[str, Any]]


def _prefetch_kb_context(state: FuncDispatchState) -> dict[str, Any]:
    dispatch = state["dispatch"]
    payload = dict(dispatch.payload or {})
    robot_id = payload.get("robot_instance_id")
    project_id = payload.get("project_id")
    ctx = KnowledgeToolContext(
        robot_instance_id=int(robot_id) if robot_id else None,
        project_id=int(project_id) if project_id else None,
        max_calls=1,
    )
    agent_ctx = fetch_agent_context(ctx)
    if agent_ctx.get("rag_policy"):
        ctx.max_calls = min(1, int(agent_ctx["rag_policy"].get("exec_max_rag_calls", 1)))
    task_hint = str(payload.get("agent_task") or payload.get("task_text") or "")[:300]
    data = query_knowledge_http(
        query=task_hint or "测试执行 UI 元素 步骤经验",
        doc_types=["execution_hint", "ui_element", "page_model", "case"],
        ctx=ctx,
        limit=3,
    )
    parts = []
    for hit in data.get("items") or []:
        parts.append(f"【{hit.get('doc_type','')} {hit.get('title','')}】\n{hit.get('snippet','')}")
    kb_block = "\n\n".join(parts)
    if kb_block.strip():
        payload["kb_context"] = kb_block
        payload["rag_trace"] = ctx.rag_trace
        if payload.get("agent_task"):
            payload["agent_task"] = (
                "【知识库参考】\n" + kb_block + "\n\n" + str(payload["agent_task"])
            )
        dispatch.payload = payload
    line_cb = state.get("on_midscene_line")
    if line_cb and kb_block.strip():
        line_cb({"kind": "rag", "phase": "prefetch", "kb_context": kb_block[:1500]})
    return {"dispatch": dispatch, "rag_trace": ctx.rag_trace}


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
        exec_context=dispatch.payload,
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
    g.add_node("prefetch_kb", _prefetch_kb_context)
    g.add_node("run_autoglm", _run_autoglm)
    g.add_node("run_midscene", _run_midscene)
    g.add_node("unsupported", _unsupported)
    g.set_entry_point("prefetch_kb")
    g.add_conditional_edges(
        "prefetch_kb",
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
