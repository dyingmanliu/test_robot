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


@dataclass
class AutoglmCallbacks:
    on_step: Callable[[int, StepResult], None] | None = None
    should_cancel: Callable[[], bool] | None = None


class AutoglmState(TypedDict, total=False):
    task: str
    agent: PhoneTestAgent
    callbacks: AutoglmCallbacks
    is_first: bool
    last_step: StepResult | None
    outcome: AgentRunOutcome | None
    cancelled: bool


def _init_node(state: AutoglmState) -> dict[str, Any]:
    state["agent"].reset()
    return {"is_first": True, "cancelled": False, "last_step": None}


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
    g.add_node("step", _step_node)
    g.add_node("finish_ok", _finish_ok)
    g.add_node("finish_cancel", _finish_cancel)
    g.add_node("finish_max", _finish_max)
    g.set_entry_point("init")
    g.add_edge("init", "step")
    g.add_conditional_edges(
        "step",
        _route_after_step,
        {
            "continue": "step",
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
) -> AgentRunOutcome:
    agent = build_phone_test_agent(device_platform=device_platform, device_id=device_id)
    graph = build_autoglm_exec_graph()
    final = graph.invoke(
        {
            "task": task.strip(),
            "agent": agent,
            "callbacks": AutoglmCallbacks(on_step=on_step, should_cancel=should_cancel),
        }
    )
    outcome = final.get("outcome")
    if outcome is not None:
        return outcome
    return AgentRunOutcome(False, "执行失败")
