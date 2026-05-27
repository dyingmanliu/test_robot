"""LangChain 平台配置。"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_AGENT_SERVICE_ROOT = Path(__file__).resolve().parents[1]
_ENV_FILE = _AGENT_SERVICE_ROOT / ".env"
if _ENV_FILE.is_file():
    load_dotenv(_ENV_FILE)


def web_internal_api_url() -> str:
    return (
        os.getenv("WEB_INTERNAL_API_URL") or os.getenv("AGENT_WEB_URL") or "http://127.0.0.1:8000"
    ).rstrip("/")


def web_service_token() -> str:
    return (os.getenv("WEB_SERVICE_TOKEN") or "").strip()


def _env_truthy(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


def _env_falsy(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("0", "false", "no", "off")


def langsmith_api_key() -> str:
    return (os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY") or "").strip()


def langchain_tracing_enabled() -> bool:
    if _env_falsy("LANGCHAIN_TRACING_V2") or _env_falsy("LANGSMITH_TRACING"):
        return False
    if _env_truthy("LANGCHAIN_TRACING_V2") or _env_truthy("LANGSMITH_TRACING"):
        return bool(langsmith_api_key())
    # 仅配置 API Key 时默认开启（便于本地集成 LangSmith）
    return bool(langsmith_api_key())


def langsmith_project() -> str:
    return (
        os.getenv("LANGCHAIN_PROJECT")
        or os.getenv("LANGSMITH_PROJECT")
        or "test-robots"
    ).strip()


def configure_langsmith() -> bool:
    """写入 LangChain/LangSmith 追踪所需环境变量（须在首次 LangChain 调用前执行）。"""
    api_key = langsmith_api_key()
    if not api_key or not langchain_tracing_enabled():
        return False

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = api_key
    os.environ["LANGSMITH_API_KEY"] = api_key

    project = langsmith_project()
    if project:
        os.environ["LANGCHAIN_PROJECT"] = project
        os.environ["LANGSMITH_PROJECT"] = project

    endpoint = (
        os.getenv("LANGCHAIN_ENDPOINT") or os.getenv("LANGSMITH_ENDPOINT") or ""
    ).strip()
    if endpoint:
        os.environ["LANGCHAIN_ENDPOINT"] = endpoint
        os.environ["LANGSMITH_ENDPOINT"] = endpoint

    return True
