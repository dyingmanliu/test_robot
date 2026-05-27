"""用例生成 LCEL 链。"""
from __future__ import annotations

import logging
import time

from langchain_core.messages import HumanMessage, SystemMessage

from agent_service.analysis_agent.config import (
    CASE_GENERATION_SYSTEM_PROMPT,
    AnalysisAgentConfig,
    kb_enabled,
    kb_limit,
    load_analysis_config,
)
from agent_service.analysis_agent.errors import AnalysisAgentError
from agent_service.analysis_agent.parser import draft_from_parsed, extract_json_object
from agent_service.analysis_agent.types import CaseDraft, ProjectContext
from agent_service.langchain_platform.models import get_chat_model
from agent_service.langchain_platform.retrievers.web_case_kb import WebCaseKbRetriever

log = logging.getLogger("langchain_platform.case_gen")


def _build_user_message(*, project: ProjectContext, prompt: str, kb_snippets: list[str]) -> str:
    user_line = prompt.strip()
    parts = [
        "【首要需求 · 必须严格执行】",
        user_line,
        "",
        "【项目背景（次要；与用户描述中的 App 冲突时忽略本段的应用设定）】",
        f"项目：{project.name}",
        f"项目默认被测应用：{project.tested_app_name or '（未填写）'}",
    ]
    objective = (project.test_objective or "").strip()
    if objective:
        parts.append(f"测试目标：{objective}")
    if kb_snippets:
        parts.append(
            "【历史用例参考（仅借鉴步骤结构与粒度；App 名称与用户描述不一致时不得采用）】\n"
            + "\n\n".join(kb_snippets)
        )
    return "\n".join(parts)


def _resolve_kb_snippets(
    *,
    prompt: str,
    kb_snippets: list[str] | None,
    project_id: int | None,
    owner_scope_ids: str | None,
) -> tuple[list[str], list[int]]:
    if kb_snippets:
        return kb_snippets, []
    if not kb_enabled() or project_id is None:
        return [], []

    retriever = WebCaseKbRetriever(
        project_id=project_id,
        owner_scope_ids=owner_scope_ids,
        limit=kb_limit(),
    )
    docs = retriever.invoke(prompt[:200])
    snippets = [d.page_content for d in docs if d.page_content.strip()]
    case_ids: list[int] = []
    for d in docs:
        cid = d.metadata.get("case_id")
        if isinstance(cid, int):
            case_ids.append(cid)
    return snippets, case_ids


class CaseGenChain:
    def __init__(self, config: AnalysisAgentConfig | None = None) -> None:
        self.config = config or load_analysis_config()
        self._llm = get_chat_model(
            "case_gen",
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            timeout=self.config.timeout_sec,
        )

    def generate(
        self,
        *,
        project: ProjectContext,
        prompt: str,
        kb_snippets: list[str] | None = None,
        project_id: int | None = None,
        owner_scope_ids: str | None = None,
    ) -> CaseDraft:
        text = (prompt or "").strip()
        if not text:
            raise AnalysisAgentError("请填写用例描述")
        if len(text) > 2000:
            raise AnalysisAgentError("描述不能超过 2000 字")
        if not self.config.api_key:
            raise AnalysisAgentError(
                "未配置用例生成 API Key，请在 .env 中设置 CASE_GEN_API_KEY 或 BIGMODEL_API_KEY"
            )

        resolved_snippets, similar_ids = _resolve_kb_snippets(
            prompt=text,
            kb_snippets=kb_snippets,
            project_id=project_id,
            owner_scope_ids=owner_scope_ids,
        )

        user_msg = _build_user_message(project=project, prompt=text, kb_snippets=resolved_snippets)
        messages = [
            SystemMessage(content=CASE_GENERATION_SYSTEM_PROMPT),
            HumanMessage(content=user_msg),
        ]
        log.info(
            "LangChain 用例生成开始 model=%s project=%r kb_refs=%s",
            self.config.model_name,
            project.name,
            len(resolved_snippets),
        )
        t0 = time.perf_counter()
        try:
            resp = self._llm.invoke(messages)
        except Exception as e:
            raise AnalysisAgentError(f"调用大模型失败：{e}") from e
        raw = str(resp.content or "").strip()
        if not raw:
            raise AnalysisAgentError("模型返回为空")
        try:
            draft = draft_from_parsed(extract_json_object(raw))
        except AnalysisAgentError:
            fix_messages = messages + [
                resp,
                HumanMessage(
                    content="上次输出无法解析。请仅输出符合要求的单个 JSON 对象，不要 markdown。"
                ),
            ]
            resp2 = self._llm.invoke(fix_messages)
            raw2 = str(resp2.content or "").strip()
            draft = draft_from_parsed(extract_json_object(raw2))

        draft.model = self.config.model_name
        if similar_ids:
            draft.similar_case_ids = similar_ids
        log.info(
            "LangChain 用例生成完成 title=%r steps=%s elapsed=%.0fms",
            draft.title,
            len(draft.steps),
            (time.perf_counter() - t0) * 1000,
        )
        return draft
