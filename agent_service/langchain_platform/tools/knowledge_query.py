"""知识库 Agentic RAG Tools（HTTP → Web internal API）。"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from agent_service.langchain_platform.config import web_internal_api_url, web_service_token

log = logging.getLogger(__name__)


@dataclass
class KnowledgeToolContext:
    robot_instance_id: int | None = None
    project_id: int | None = None
    owner_scope_ids: str | None = None
    rag_calls: int = 0
    max_calls: int = 5
    rag_trace: list[dict[str, Any]] = field(default_factory=list)
    on_progress: Callable[[dict[str, Any]], None] | None = None


def _internal_headers() -> dict[str, str]:
    token = web_service_token()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def query_knowledge_http(
    *,
    query: str,
    doc_types: list[str] | None,
    ctx: KnowledgeToolContext,
    limit: int = 5,
) -> dict[str, Any]:
    if ctx.rag_calls >= ctx.max_calls:
        return {"items": [], "error": "已达到 RAG 调用上限"}
    ctx.rag_calls += 1
    url = f"{web_internal_api_url()}/api/internal/knowledge/query"
    payload: dict[str, Any] = {
        "query": query,
        "doc_types": doc_types or [],
        "limit": limit,
        "project_id": ctx.project_id,
        "owner_scope_ids": ctx.owner_scope_ids,
    }
    if ctx.robot_instance_id is not None:
        payload["robot_instance_id"] = ctx.robot_instance_id
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, json=payload, headers=_internal_headers())
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        log.warning("query_knowledge 失败: %s", exc)
        data = {"items": [], "error": str(exc)}
    ctx.rag_trace.append(
        {
            "call_index": ctx.rag_calls,
            "tool": "query_knowledge",
            "query": query,
            "doc_types": doc_types or [],
            "hits": data.get("items") or [],
            "latency_ms": data.get("latency_ms"),
        }
    )
    if ctx.on_progress is not None:
        from agent_service.analysis_agent.progress import emit_kb_http_log

        emit_kb_http_log(
            ctx.on_progress,
            query=query,
            doc_types=doc_types,
            data=data,
            call_index=ctx.rag_calls,
        )
    return data


def fetch_agent_context(ctx: KnowledgeToolContext) -> dict[str, Any]:
    if ctx.robot_instance_id is None:
        return {}
    url = f"{web_internal_api_url()}/api/internal/robots/{ctx.robot_instance_id}/agent-context"
    params: dict[str, Any] = {}
    if ctx.project_id is not None:
        params["project_id"] = ctx.project_id
    if ctx.owner_scope_ids:
        params["owner_scope_ids"] = ctx.owner_scope_ids
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(url, params=params, headers=_internal_headers())
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        log.warning("fetch_agent_context 失败: %s", exc)
        return {}


class QueryKnowledgeInput(BaseModel):
    query: str = Field(description="检索问题或关键词")
    doc_types: str = Field(
        default="",
        description="可选，逗号分隔 doc_type：standard,case,page_model,ui_element,execution_hint 等",
    )


def _format_hits(data: dict[str, Any]) -> str:
    items = data.get("items") or []
    if not items:
        return "未找到相关知识片段。"
    parts: list[str] = []
    for it in items:
        title = it.get("title") or ""
        snippet = it.get("snippet") or ""
        dtype = it.get("doc_type") or ""
        parts.append(f"【{dtype} {title}】\n{snippet}")
    return "\n\n".join(parts)


def build_query_knowledge_tool(ctx: KnowledgeToolContext) -> BaseTool:
    def _run(query: str, doc_types: str = "") -> str:
        dtypes = [x.strip() for x in doc_types.split(",") if x.strip()] or None
        data = query_knowledge_http(query=query, doc_types=dtypes, ctx=ctx)
        return _format_hits(data)

    return StructuredTool.from_function(
        func=_run,
        name="query_knowledge",
        description="从绑定的企业知识库语义检索测试规范、用例、页面模型、UI 元素、执行经验等。",
        args_schema=QueryKnowledgeInput,
    )


def build_search_ui_element_tool(ctx: KnowledgeToolContext) -> BaseTool:
    def _run(query: str, doc_types: str = "ui_element,page_model") -> str:
        dtypes = [x.strip() for x in doc_types.split(",") if x.strip()]
        data = query_knowledge_http(query=query, doc_types=dtypes, ctx=ctx)
        return _format_hits(data)

    return StructuredTool.from_function(
        func=_run,
        name="search_ui_element",
        description="检索 UI 元素定义与页面模型。",
        args_schema=QueryKnowledgeInput,
    )


def build_search_execution_hint_tool(ctx: KnowledgeToolContext) -> BaseTool:
    def _run(query: str, doc_types: str = "execution_hint,case") -> str:
        dtypes = [x.strip() for x in doc_types.split(",") if x.strip()]
        data = query_knowledge_http(query=query, doc_types=dtypes, ctx=ctx)
        return _format_hits(data)

    return StructuredTool.from_function(
        func=_run,
        name="search_execution_hint",
        description="检索历史执行经验与相似用例步骤。",
        args_schema=QueryKnowledgeInput,
    )


class ValidateDraftInput(BaseModel):
    draft_json: str = Field(description="待校验的用例 JSON 字符串")


def build_validate_case_draft_tool() -> BaseTool:
    def _run(draft_json: str) -> str:
        try:
            data = json.loads(draft_json)
        except json.JSONDecodeError as e:
            return f"无效 JSON：{e}"
        if not (data.get("title") or "").strip():
            return "缺少 title"
        steps = data.get("steps") or []
        if not isinstance(steps, list) or len(steps) < 1:
            return "至少需要一个步骤"
        for i, s in enumerate(steps, start=1):
            if not isinstance(s, dict):
                return f"步骤 {i} 格式无效"
            if not str(s.get("description") or "").strip():
                return f"步骤 {i} 缺少 description"
        return "ok"

    return StructuredTool.from_function(
        func=_run,
        name="validate_case_draft",
        description="校验用例草稿 JSON 是否包含 title 与有效 steps。",
        args_schema=ValidateDraftInput,
    )


def build_tools_for_context(
    ctx: KnowledgeToolContext,
    skill_names: list[str] | None = None,
) -> list[BaseTool]:
    from agent_service.langchain_platform.tools.device_autoglm import list_connected_devices_hint
    from agent_service.langchain_platform.tools.registry import list_skills

    catalog_skills = set(list_skills("test_analysis") + list_skills("functional_execution"))
    allowed = set(skill_names or catalog_skills)
    mapping: dict[str, Callable[[], BaseTool]] = {
        "query_knowledge": lambda: build_query_knowledge_tool(ctx),
        "query_feature_context": lambda: build_query_knowledge_tool(ctx),
        "search_ui_element": lambda: build_search_ui_element_tool(ctx),
        "search_execution_hint": lambda: build_search_execution_hint_tool(ctx),
        "validate_case_draft": build_validate_case_draft_tool,
        "preflight_device": lambda: list_connected_devices_hint,
    }
    tools: list[BaseTool] = []
    for name in allowed:
        factory = mapping.get(name)
        if factory:
            tools.append(factory())
    return tools
