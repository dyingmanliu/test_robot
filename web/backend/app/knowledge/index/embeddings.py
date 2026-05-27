"""DashScope Embedding（OpenAI 兼容 HTTP，绕过 LlamaIndex 模型枚举限制）。"""
from __future__ import annotations

from functools import lru_cache

from openai import OpenAI

from app.knowledge.config import (
    kb_embedding_api_key,
    kb_embedding_base_url,
    kb_embedding_model,
)


class DashScopeEmbedding:
    """OpenAI-compatible embedding client for DashScope text-embedding-v3."""

    def __init__(self, *, api_key: str, api_base: str, model: str) -> None:
        self._client = OpenAI(api_key=api_key, base_url=api_base)
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
    if "403" in msg or "forbidden" in lower:
        return "Embedding API 访问被拒绝，请检查 Key 权限或账户状态。"
    return msg[:600]
