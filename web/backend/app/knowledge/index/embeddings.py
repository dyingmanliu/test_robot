"""DashScope Embedding（OpenAI 兼容 HTTP，绕过 LlamaIndex 模型枚举限制）。"""
from __future__ import annotations

import os
from functools import lru_cache

import httpx
from openai import OpenAI

from app.knowledge.config import (
    kb_embedding_api_key,
    kb_embedding_base_url,
    kb_embedding_model,
)


def _http_trust_env() -> bool:
    """默认不读系统 HTTP_PROXY，避免 Cursor/本机代理拦截 Embedding（403 / Connection error）。"""
    return os.getenv("KB_EMBEDDING_HTTP_TRUST_ENV", "").strip().lower() in ("1", "true", "yes")


class DashScopeEmbedding:
    """OpenAI-compatible embedding client for DashScope text-embedding-v3."""

    def __init__(self, *, api_key: str, api_base: str, model: str) -> None:
        http_client = httpx.Client(trust_env=_http_trust_env(), timeout=60.0)
        self._client = OpenAI(api_key=api_key, base_url=api_base, http_client=http_client)
        self._model = model

    def get_text_embedding(self, text: str) -> list[float]:
        resp = self._client.embeddings.create(input=text, model=self._model)
        return list(resp.data[0].embedding)


@lru_cache(maxsize=1)
def get_embed_model() -> DashScopeEmbedding | None:
    key = kb_embedding_api_key()
    if not key:
        return None
    return DashScopeEmbedding(
        api_key=key,
        api_base=kb_embedding_base_url(),
        model=kb_embedding_model(),
    )


def format_embedding_error(exc: Exception) -> str:
    """将 OpenAI/DashScope 异常转为用户可读提示。"""
    msg = str(exc)
    lower = msg.lower()
    if "arrearage" in lower or "overdue-payment" in lower:
        return (
            "DashScope（阿里云百炼）账户欠费或停服，无法生成向量。"
            "请登录阿里云充值或续费 Model Studio 后重试；"
            "或在 web/backend/.env 更换有效的 KB_EMBEDDING_API_KEY / 兼容 Embedding 网关。"
        )
    if "401" in msg or "invalid_api_key" in lower or "incorrect api key" in lower:
        return "Embedding API Key 无效，请检查 web/backend/.env 中的 KB_EMBEDDING_API_KEY。"
    if "403" in msg or "forbidden" in lower or "proxyerror" in lower:
        return (
            "Embedding 请求被本机 HTTP 代理拦截（403）。"
            "请关闭 VPN/系统代理，或确认 web/backend 已加载 KB_EMBEDDING 直连配置后重启后端。"
        )
    if "connection error" in lower:
        return (
            "无法连接 Embedding 服务，请检查网络、KB_EMBEDDING_BASE_URL 与 API Key；"
            "若本机设置了 HTTP_PROXY，可重启后端（默认已绕过系统代理）。"
        )
    return msg[:600]
