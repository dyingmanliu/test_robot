"""OpenAI 兼容非流式客户端（用例 JSON 生成）。"""

from __future__ import annotations

import logging
from typing import Any

from openai import OpenAI

from analysis_agent.config import AnalysisAgentConfig
from analysis_agent.errors import AnalysisAgentError

log = logging.getLogger(__name__)


class AnalysisModelClient:
    def __init__(self, config: AnalysisAgentConfig) -> None:
        self.config = config
        self._client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout_sec,
        )

    def chat(self, messages: list[dict[str, str]]) -> str:
        log.debug(
            "chat.completions model=%s messages=%s",
            self.config.model_name,
            len(messages),
        )
        try:
            resp = self._client.chat.completions.create(
                model=self.config.model_name,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                timeout=self.config.timeout_sec,
            )
        except Exception as e:
            log.warning("analysis_agent LLM call failed: %s", e)
            raise AnalysisAgentError(f"调用大模型失败：{e}") from e
        content = resp.choices[0].message.content if resp.choices else None
        if not content or not str(content).strip():
            raise AnalysisAgentError("模型返回为空")
        return str(content)
