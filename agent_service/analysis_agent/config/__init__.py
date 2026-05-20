"""配置加载（仓库根 `.env`）。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from agent_service.analysis_agent.config.prompts import CASE_GENERATION_SYSTEM_PROMPT

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _REPO_ROOT / ".env"
if _ENV_FILE.is_file():
    load_dotenv(_ENV_FILE)


@dataclass
class AnalysisAgentConfig:
    api_key: str
    base_url: str
    model_name: str
    timeout_sec: float
    temperature: float = 0.3
    max_tokens: int = 4096


def _env_bool(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def load_analysis_config() -> AnalysisAgentConfig:
    api_key = (
        (os.getenv("CASE_GEN_API_KEY") or "").strip()
        or (os.getenv("BIGMODEL_API_KEY") or "").strip()
        or (os.getenv("ZHIPU_API_KEY") or "").strip()
    )
    base_url = (
        (os.getenv("CASE_GEN_BASE_URL") or "").strip()
        or (os.getenv("OPENAI_BASE_URL") or "").strip()
        or "https://open.bigmodel.cn/api/paas/v4"
    )
    model = (os.getenv("CASE_GEN_MODEL") or "").strip() or "glm-4-flash"
    timeout_sec = float(os.getenv("CASE_GEN_TIMEOUT_SEC", "60"))
    return AnalysisAgentConfig(
        api_key=api_key,
        base_url=base_url,
        model_name=model,
        timeout_sec=timeout_sec,
    )


def kb_enabled() -> bool:
    return _env_bool("CASE_GEN_USE_KB", True)


def kb_limit() -> int:
    return max(1, min(5, int(os.getenv("CASE_GEN_KB_LIMIT", "3"))))


__all__ = [
    "AnalysisAgentConfig",
    "CASE_GENERATION_SYSTEM_PROMPT",
    "kb_enabled",
    "kb_limit",
    "load_analysis_config",
]
