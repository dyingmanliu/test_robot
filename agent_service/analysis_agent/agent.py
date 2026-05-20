"""用例分析 / 编写 Agent：一句话 → structured 测试用例草稿。"""

from __future__ import annotations

import logging
import time

from agent_service.analysis_agent.config import (
    CASE_GENERATION_SYSTEM_PROMPT,
    AnalysisAgentConfig,
    load_analysis_config,
)
from agent_service.analysis_agent.errors import AnalysisAgentError
from agent_service.analysis_agent.model.client import AnalysisModelClient
from agent_service.analysis_agent.parser import draft_from_parsed, extract_json_object
from agent_service.analysis_agent.types import CaseDraft, ProjectContext

log = logging.getLogger("analysis_agent")


class AnalysisAgent:
    """与 PhoneTestAgent 类似：配置 + ModelClient，对外提供高层 generate 方法。"""

    def __init__(self, config: AnalysisAgentConfig | None = None) -> None:
        self.config = config or load_analysis_config()
        self._client = AnalysisModelClient(self.config)

    def generate_case_draft(
        self,
        *,
        project: ProjectContext,
        prompt: str,
        kb_snippets: list[str] | None = None,
    ) -> CaseDraft:
        """根据一句话生成 structured 用例草稿（不写库）。"""
        text = (prompt or "").strip()
        if not text:
            raise AnalysisAgentError("请填写用例描述")
        if len(text) > 2000:
            raise AnalysisAgentError("描述不能超过 2000 字")

        if not self.config.api_key:
            raise AnalysisAgentError(
                "未配置用例生成 API Key，请在 .env 中设置 CASE_GEN_API_KEY 或 BIGMODEL_API_KEY"
            )

        user_msg = self._build_user_message(
            project=project,
            prompt=text,
            kb_snippets=kb_snippets or [],
        )
        messages: list[dict[str, str]] = [
            {"role": "system", "content": CASE_GENERATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        log.info(
            "LLM 用例生成开始 model=%s project=%r kb_refs=%s prompt_len=%s",
            self.config.model_name,
            project.name,
            len(kb_snippets or []),
            len(text),
        )
        t0 = time.perf_counter()
        raw = self._client.chat(messages)
        try:
            draft = draft_from_parsed(extract_json_object(raw))
        except AnalysisAgentError:
            log.warning("LLM 首次 JSON 解析失败，重试修复 project=%r", project.name)
            fix_messages = messages + [
                {"role": "assistant", "content": raw},
                {
                    "role": "user",
                    "content": "上次输出无法解析。请仅输出符合要求的单个 JSON 对象，不要 markdown。",
                },
            ]
            raw2 = self._client.chat(fix_messages)
            draft = draft_from_parsed(extract_json_object(raw2))

        draft.model = self.config.model_name
        elapsed_ms = (time.perf_counter() - t0) * 1000
        log.info(
            "LLM 用例生成完成 model=%s title=%r steps=%s elapsed=%.0fms",
            draft.model,
            draft.title,
            len(draft.steps),
            elapsed_ms,
        )
        return draft

    @staticmethod
    def _build_user_message(
        *,
        project: ProjectContext,
        prompt: str,
        kb_snippets: list[str],
    ) -> str:
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
