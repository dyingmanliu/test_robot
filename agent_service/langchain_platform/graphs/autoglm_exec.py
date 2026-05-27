"""AutoGLM 执行 LangGraph：observe → plan → act 循环。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, TypedDict

from langgraph.graph import END, StateGraph

from agent_service.func_agent.backends.autoglm.agent import (
    AgentConfig,
    AgentRunOutcome,
    PhoneTestAgent,
    StepResult,
)
from agent_service.langchain_platform.tools.device_autoglm import build_phone_test_agent
from agent_service.langchain_platform.tools.knowledge_query import (
    KnowledgeToolContext,
    query_knowledge_http,
)


@dataclass
class AutoglmCallbacks:
    on_step: Callable[[int, StepResult], None] | None = None
    should_cancel: Callable[[], bool] | None = None


class AutoglmState(TypedDict, total=False):
    task: str
    agent: PhoneTestAgent
    callbacks: AutoglmCallbacks
    exec_context: dict[str, Any]
    is_first: bool
    last_step: StepResult | None
    outcome: AgentRunOutcome | None
    cancelled: bool
    fail_streak: int


def _init_node(state: AutoglmState) -> dict[str, Any]:
    state["agent"].reset()
    return {"is_first": True, "cancelled": False, "last_step": None, "fail_streak": 0, "exec_context": state.get("exec_context") or {}}


def _maybe_recovery_rag(state: AutoglmState) -> dict[str, Any]:
    """步骤连续失败时触发 Recovery RAG（最多 1 次额外检索）。"""
    ctx_raw = state.get("exec_context") or {}
    if ctx_raw.get("_recovery_rag_done"):
        return {}
    streak = state.get("fail_streak") or 0
    last = state.get("last_step")
    if streak < 2 and not (last and not last.success):
        return {}
    robot_id = ctx_raw.get("robot_instance_id")
    project_id = ctx_raw.get("project_id")
    tool_ctx = KnowledgeToolContext(
        robot_instance_id=int(robot_id) if robot_id else None,
        project_id=int(project_id) if project_id else None,
        max_calls=1,
    )
    hint = str(last.message if last else "")[:200]
    data = query_knowledge_http(
        query=f"执行失败恢复 {hint}",
        doc_types=["execution_hint", "case"],
        ctx=tool_ctx,
        limit=2,
    )
    parts = []
    for hit in data.get("items") or []:
        parts.append(hit.get("snippet") or "")
    extra = "\n".join(parts).strip()
    if not extra:
        ctx_raw["_recovery_rag_done"] = True
        return {"exec_context": ctx_raw}
    new_task = state["task"] + "\n\n【Recovery 知识库参考】\n" + extra
    ctx_raw["_recovery_rag_done"] = True
    ctx_raw.setdefault("rag_trace", []).extend(tool_ctx.rag_trace)
    return {"task": new_task, "exec_context": ctx_raw, "fail_streak": 0}


def _step_node(state: AutoglmState) -> dict[str, Any]:
    callbacks = state.get("callbacks") or AutoglmCallbacks()
    if callbacks.should_cancel and callbacks.should_cancel():
        return {"cancelled": True}

    agent = state["agent"]
    task = state["task"]
    is_first = state.get("is_first", False)
    if is_first:
        step = agent._execute_step(task, is_first=True)
        out: dict[str, Any] = {"last_step": step, "is_first": False}
    else:
        step = agent._execute_step(is_first=False)
        out = {"last_step": step}

    if callbacks.on_step:
        callbacks.on_step(agent._step_count, step)
    streak = state.get("fail_streak") or 0
    if not step.success:
        streak += 1
    else:
        streak = 0
    out["fail_streak"] = streak
    return out


def _route_after_step(state: AutoglmState) -> str:
    if state.get("cancelled"):
        return "end_cancel"
    step = state.get("last_step")
    if step is None:
        return "end_fail"
    if step.finished:
        return "end_ok"
    if state["agent"]._step_count >= state["agent"].agent_config.max_steps:
        return "end_max"
    return "continue"


def _finish_ok(state: AutoglmState) -> dict[str, Any]:
    step = state["last_step"]
    msg = (step.message if step else None) or "任务结束"
    ok = step.success if step else False
    return {"outcome": AgentRunOutcome(ok, msg)}


def _finish_cancel(state: AutoglmState) -> dict[str, Any]:
    return {"outcome": AgentRunOutcome(False, "执行已取消")}


def _finish_max(state: AutoglmState) -> dict[str, Any]:
    step = state.get("last_step")
    if step and step.finished:
        return {"outcome": AgentRunOutcome(step.success, step.message or "任务结束")}
    return {"outcome": AgentRunOutcome(False, "已达到最大步数限制")}


def build_autoglm_exec_graph():
    g = StateGraph(AutoglmState)
    g.add_node("init", _init_node)
    g.add_node("recovery_rag", _maybe_recovery_rag)
    g.add_node("step", _step_node)
    g.add_node("finish_ok", _finish_ok)
    g.add_node("finish_cancel", _finish_cancel)
    g.add_node("finish_max", _finish_max)
    g.set_entry_point("init")
    g.add_edge("init", "recovery_rag")
    g.add_conditional_edges(
        "recovery_rag",
        lambda s: "step",
        {"step": "step"},
    )
    g.add_conditional_edges(
        "step",
        _route_after_step,
        {
            "continue": "recovery_rag",
            "end_ok": "finish_ok",
            "end_cancel": "finish_cancel",
            "end_max": "finish_max",
            "end_fail": "finish_max",
        },
    )
    g.add_edge("finish_ok", END)
    g.add_edge("finish_cancel", END)
    g.add_edge("finish_max", END)
    return g.compile()


def run_autoglm_graph(
    task: str,
    *,
    device_platform: str = "android",
    device_id: str | None = None,
    on_step: Callable[[int, Any], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
    exec_context: dict[str, Any] | None = None,
) -> AgentRunOutcome:
    agent = build_phone_test_agent(device_platform=device_platform, device_id=device_id)
    graph = build_autoglm_exec_graph()
    final = graph.invoke(
        {
            "task": task.strip(),
            "agent": agent,
            "callbacks": AutoglmCallbacks(on_step=on_step, should_cancel=should_cancel),
            "exec_context": exec_context or {},
        }
    )
    outcome = final.get("outcome")
    if outcome is not None:
        return outcome
    return AgentRunOutcome(False, "执行失败")
