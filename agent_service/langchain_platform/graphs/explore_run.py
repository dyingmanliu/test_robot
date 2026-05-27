"""功能点分析 LangGraph 编排（含 Agentic RAG prefetch）。"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from agent_service.analysis_agent.feature_explore.tree_build import ensure_giic_tree
from agent_service.analysis_agent.feature_explore.types import (
    CancelCheck,
    ExploreDispatch,
    ExploreRunResult,
    MachineLineCallback,
)
from agent_service.langchain_platform.explore_core import execute_explore_run
from agent_service.langchain_platform.tools.knowledge_query import (
    KnowledgeToolContext,
    fetch_agent_context,
    query_knowledge_http,
)


class ExploreState(TypedDict, total=False):
    dispatch: ExploreDispatch
    on_machine_line: MachineLineCallback | None
    should_cancel: CancelCheck | None
    log_model_usage: MachineLineCallback | None
    result: ExploreRunResult | None
    error: str | None
    rag_trace: list[dict[str, Any]]


def _validate_dispatch(state: ExploreState) -> dict[str, Any]:
    dispatch = state["dispatch"]
    if not (dispatch.app_name or "").strip():
        return {"error": "缺少 app_name"}
    if not (dispatch.device_platform or "").strip():
        return {"error": "缺少 device_platform"}
    return {}


def _prefetch_kb_context(state: ExploreState) -> dict[str, Any]:
    if state.get("error"):
        return {}
    dispatch = state["dispatch"]
    ctx = KnowledgeToolContext(
        robot_instance_id=dispatch.robot_instance_id,
        project_id=dispatch.project_id,
        max_calls=2,
    )
    agent_ctx = fetch_agent_context(ctx)
    if agent_ctx.get("rag_policy"):
        ctx.max_calls = min(2, int(agent_ctx["rag_policy"].get("max_calls", 2)))
    query = f"{dispatch.app_name} 功能清单 测试规范 页面模型"
    data = query_knowledge_http(
        query=query,
        doc_types=["feature_list", "standard", "page_model", "feature_tree"],
        ctx=ctx,
        limit=3,
    )
    parts = []
    for hit in data.get("items") or []:
        parts.append(f"【{hit.get('doc_type','')} {hit.get('title','')}】\n{hit.get('snippet','')}")
    kb_context = "\n\n".join(parts)
    dispatch.kb_context = kb_context
    cb = state.get("on_machine_line")
    if cb and kb_context.strip():
        cb({"kind": "rag", "phase": "prefetch", "kb_context": kb_context[:2000], "rag_trace": ctx.rag_trace})
    return {"dispatch": dispatch, "rag_trace": ctx.rag_trace}


def _run_explore(state: ExploreState) -> dict[str, Any]:
    if state.get("error"):
        return {}
    result = execute_explore_run(
        state["dispatch"],
        on_machine_line=state.get("on_machine_line"),
        should_cancel=state.get("should_cancel"),
        log_model_usage=state.get("log_model_usage"),
    )
    return {"result": result}


def _sync_tree(state: ExploreState) -> dict[str, Any]:
    result = state.get("result")
    if result is None or result.tree is None:
        return {}
    tree = ensure_giic_tree(result.tree)
    return {"result": ExploreRunResult(ok=result.ok, message=result.message, tree=tree, report_file=result.report_file)}


def _route_after_validate(state: ExploreState) -> str:
    return "fail" if state.get("error") else "prefetch"


def _finish_error(state: ExploreState) -> dict[str, Any]:
    msg = state.get("error") or "校验失败"
    return {"result": ExploreRunResult(ok=False, message=msg)}


def build_explore_orchestrator_graph():
    g = StateGraph(ExploreState)
    g.add_node("validate", _validate_dispatch)
    g.add_node("prefetch_kb", _prefetch_kb_context)
    g.add_node("run_explore", _run_explore)
    g.add_node("sync_tree", _sync_tree)
    g.add_node("finish_error", _finish_error)
    g.set_entry_point("validate")
    g.add_conditional_edges("validate", _route_after_validate, {"prefetch": "prefetch_kb", "fail": "finish_error"})
    g.add_edge("prefetch_kb", "run_explore")
    g.add_edge("run_explore", "sync_tree")
    g.add_edge("sync_tree", END)
    g.add_edge("finish_error", END)
    return g.compile()


def run_explore_graph(
    dispatch: ExploreDispatch,
    *,
    on_machine_line: MachineLineCallback | None = None,
    should_cancel: CancelCheck | None = None,
    log_model_usage: MachineLineCallback | None = None,
) -> ExploreRunResult:
    graph = build_explore_orchestrator_graph()
    final = graph.invoke(
        {
            "dispatch": dispatch,
            "on_machine_line": on_machine_line,
            "should_cancel": should_cancel,
            "log_model_usage": log_model_usage,
        }
    )
    result = final.get("result")
    if result is not None:
        return result
    return ExploreRunResult(ok=False, message=final.get("error") or "功能点分析失败")
