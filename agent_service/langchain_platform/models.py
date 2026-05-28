"""ChatOpenAI 工厂：按 profile 读取 CASE_GEN_* / BIGMODEL_* 环境变量。"""

from __future__ import annotations

import os
from typing import Literal

import httpx
from langchain_openai import ChatOpenAI

ModelProfile = Literal["case_gen", "autoglm"]


def _http_trust_env() -> bool:
    """默认不读系统 HTTP_PROXY，避免 Cursor/本机代理拦截 LLM 请求（403）。"""
    return os.getenv("CASE_GEN_HTTP_TRUST_ENV", "").strip().lower() in ("1", "true", "yes")


def _httpx_client(timeout_sec: float) -> httpx.Client:
    timeout = httpx.Timeout(timeout_sec, connect=min(30.0, timeout_sec))
    return httpx.Client(trust_env=_http_trust_env(), timeout=timeout)


def _case_gen_credentials() -> tuple[str, str, str]:
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
    return api_key, base_url, model


def get_chat_model(
    profile: ModelProfile = "case_gen",
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout: float | None = None,
) -> ChatOpenAI:
    if profile == "case_gen":
        api_key, base_url, model = _case_gen_credentials()
        temp = 0.3 if temperature is None else temperature
        to = float(os.getenv("CASE_GEN_TIMEOUT_SEC", "60")) if timeout is None else timeout
    else:
        api_key = (os.getenv("BIGMODEL_API_KEY") or "").strip() or (os.getenv("ZHIPU_API_KEY") or "").strip()
        base_url = (os.getenv("OPENAI_BASE_URL") or "").strip() or "https://open.bigmodel.cn/api/paas/v4"
        model = (os.getenv("PHONE_AGENT_MODEL") or "").strip() or "autoglm-phone"
        temp = 0.1 if temperature is None else temperature
        to = float(os.getenv("PHONE_AGENT_TIMEOUT_SEC", "120")) if timeout is None else timeout

    return ChatOpenAI(
        model=model,
        api_key=api_key or None,
        base_url=base_url,
        temperature=temp,
        max_tokens=max_tokens or 4096,
        timeout=to,
        max_retries=2,
        http_client=_httpx_client(to),
    )
