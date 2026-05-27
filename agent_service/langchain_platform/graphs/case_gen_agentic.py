"""用例生成 Agentic RAG LangGraph。"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from agent_service.analysis_agent.config import (
    CASE_GENERATION_SYSTEM_PROMPT,
    AnalysisAgentConfig,
    load_analysis_config,
)
from agent_service.analysis_agent.errors import AnalysisAgentError
from agent_service.analysis_agent.parser import draft_from_parsed, extract_json_object
from agent_service.analysis_agent.types import CaseDraft, ProjectContext
from agent_service.langchain_platform.models import get_chat_model
from agent_service.langchain_platform.tools.knowledge_query import (
    KnowledgeToolContext,
    fetch_agent_context,
    query_knowledge_http,
)

log = logging.getLogger("langchain_platform.case_gen_agentic")


class CaseGenAgenticState(TypedDict, total=False):
    project: ProjectContext
    prompt: str
    robot_instance_id: int | None
    project_id: int | None
    owner_scope_ids: str | None
    rag_mode: str
    kb_context: str
    rag_trace: list[dict[str, Any]]
    draft: CaseDraft | None
    error: str | None
    tool_ctx: KnowledgeToolContext


def _rag_mode() -> str:
    return (os.getenv("RAG_DEFAULT_MODE") or "agentic").strip().lower()


def _load_context(state: CaseGenAgenticState) -> dict[str, Any]:
    ctx = KnowledgeToolContext(
        robot_instance_id=state.get("robot_instance_id"),
        project_id=state.get("project_id"),
        owner_scope_ids=state.get("owner_scope_ids"),
        max_calls=5,
    )
    agent_ctx = fetch_agent_context(ctx)
    if agent_ctx.get("rag_policy"):
        ctx.max_calls = int(agent_ctx["rag_policy"].get("max_calls", ctx.max_calls))
    return {"tool_ctx": ctx, "rag_trace": []}


def _agentic_retrieve(state: CaseGenAgenticState) -> dict[str, Any]:
    mode = (state.get("rag_mode") or _rag_mode()).lower()
    ctx = state["tool_ctx"]
    prompt = state["prompt"]
    if mode == "passive":
        data = query_knowledge_http(
            query=prompt[:200],
            doc_types=["case", "standard", "strategy"],
            ctx=ctx,
            limit=3,
        )
        items = data.get("items") or []
        snippets = [f"【{it.get('title','')}】\n{it.get('snippet','')}" for it in items]
        return {"kb_context": "\n\n".join(snippets), "rag_trace": ctx.rag_trace}

    # 多轮检索（避免 DeepSeek thinking 模型与 bind_tools 循环不兼容）
    _ = fetch_agent_context(ctx)
    plan_queries: list[tuple[str, list[str]]] = [
        (prompt[:200], ["standard", "strategy", "case"]),
        (f"页面与 UI {prompt[:120]}", ["page_model", "ui_element"]),
        (f"执行经验 {prompt[:120]}", ["execution_hint", "case"]),
    ]
    for q, dtypes in plan_queries:
        if ctx.rag_calls >= ctx.max_calls:
            break
        query_knowledge_http(query=q, doc_types=dtypes, ctx=ctx, limit=3)
    summary = ""
    parts = []
    for tr in ctx.rag_trace:
        for hit in tr.get("hits") or []:
            parts.append(f"【{hit.get('doc_type','')} {hit.get('title','')}】\n{hit.get('snippet','')}")
    kb = "\n\n".join(parts)
    if summary and summary.strip() != "检索完成":
        kb = (kb + "\n\n【检索摘要】\n" + summary).strip()
    return {"kb_context": kb, "rag_trace": ctx.rag_trace}


def _generate_draft(state: CaseGenAgenticState, config: AnalysisAgentConfig) -> dict[str, Any]:
    project = state["project"]
    prompt = state["prompt"]
    kb = state.get("kb_context") or ""
    parts = [
        "【首要需求 · 必须严格执行】",
        prompt.strip(),
        "",
        "【项目背景】",
        f"项目：{project.name}",
        f"项目默认被测应用：{project.tested_app_name or '（未填写）'}",
    ]
    obj = (project.test_objective or "").strip()
    if obj:
        parts.append(f"测试目标：{obj}")
    if kb.strip():
        parts.append("【知识库参考（规范/用例/页面模型等）】\n" + kb)
    user_msg = "\n".join(parts)
    llm = get_chat_model(
        "case_gen",
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        timeout=config.timeout_sec,
    )
    messages = [
        SystemMessage(content=CASE_GENERATION_SYSTEM_PROMPT),
        HumanMessage(content=user_msg),
    ]
    resp = llm.invoke(messages)
    raw = str(resp.content or "").strip()
    try:
        draft = draft_from_parsed(extract_json_object(raw))
    except AnalysisAgentError:
        fix = messages + [
            resp,
            HumanMessage(content="请仅输出符合要求的单个 JSON 对象，不要 markdown。"),
        ]
        resp2 = llm.invoke(fix)
        draft = draft_from_parsed(extract_json_object(str(resp2.content or "")))
    draft.model = config.model_name
    similar_ids: list[int] = []
    for tr in state.get("rag_trace") or []:
        for hit in tr.get("hits") or []:
            if hit.get("doc_type") == "case" and hit.get("document_id"):
                similar_ids.append(int(hit["document_id"]))
    if similar_ids:
        draft.similar_case_ids = similar_ids[:10]
    return {"draft": draft}


def build_case_gen_agentic_graph(config: AnalysisAgentConfig | None = None):
    cfg = config or load_analysis_config()

    def gen_node(state: CaseGenAgenticState) -> dict[str, Any]:
        return _generate_draft(state, cfg)

    g = StateGraph(CaseGenAgenticState)
    g.add_node("load_context", _load_context)
    g.add_node("retrieve", _agentic_retrieve)
    g.add_node("generate", gen_node)
    g.set_entry_point("load_context")
    g.add_edge("load_context", "retrieve")
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", END)
    return g.compile()


def run_case_gen_agentic(
    *,
    project: ProjectContext,
    prompt: str,
    robot_instance_id: int | None = None,
    project_id: int | None = None,
    owner_scope_ids: str | None = None,
    rag_mode: str | None = None,
    config: AnalysisAgentConfig | None = None,
) -> tuple[CaseDraft, list[dict[str, Any]]]:
    text = (prompt or "").strip()
    if not text:
        raise AnalysisAgentError("请填写用例描述")
    if len(text) > 2000:
        raise AnalysisAgentError("描述不能超过 2000 字")
    cfg = config or load_analysis_config()
    if not cfg.api_key:
        raise AnalysisAgentError("未配置用例生成 API Key")
    graph = build_case_gen_agentic_graph(cfg)
    t0 = time.perf_counter()
    final = graph.invoke(
        {
            "project": project,
            "prompt": text,
            "robot_instance_id": robot_instance_id,
            "project_id": project_id,
            "owner_scope_ids": owner_scope_ids,
            "rag_mode": rag_mode or _rag_mode(),
        }
    )
    draft = final.get("draft")
    if draft is None:
        raise AnalysisAgentError(final.get("error") or "用例生成失败")
    trace = final.get("rag_trace") or []
    log.info(
        "Agentic 用例生成完成 title=%r rag_calls=%s elapsed=%.0fms",
        draft.title,
        len(trace),
        (time.perf_counter() - t0) * 1000,
    )
    return draft, trace
