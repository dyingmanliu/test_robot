"""知识库环境配置。"""
from __future__ import annotations

import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]


def qdrant_url() -> str:
    return (os.getenv("QDRANT_URL") or "http://127.0.0.1:6333").strip()


def qdrant_collection() -> str:
    return (os.getenv("QDRANT_COLLECTION") or "tcm_knowledge_chunks").strip()


def kb_embedding_api_key() -> str:
    return (
        (os.getenv("KB_EMBEDDING_API_KEY") or "").strip()
        or (os.getenv("MIDSCENE_MODEL_API_KEY") or "").strip()
        or (os.getenv("DASHSCOPE_API_KEY") or "").strip()
    )


def kb_embedding_base_url() -> str:
    return (
        (os.getenv("KB_EMBEDDING_BASE_URL") or "").strip()
        or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )


def kb_embedding_model() -> str:
    return (os.getenv("KB_EMBEDDING_MODEL") or "text-embedding-v3").strip()


def kb_file_storage() -> Path:
    raw = (os.getenv("KB_FILE_STORAGE") or "web/backend/data/knowledge").strip()
    p = Path(raw)
    if not p.is_absolute():
        p = _REPO_ROOT / raw
    p.mkdir(parents=True, exist_ok=True)
    return p


def rag_default_mode() -> str:
    return (os.getenv("RAG_DEFAULT_MODE") or "agentic").strip().lower()


DEFAULT_CHUNK_POLICY = {
    "max_chars": 800,
    "overlap": 100,
    "overlap_short": 80,
    "prefix_title": True,
    "prefix_section": True,
    "heading_aware": True,
    "search_min_score": None,
}


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def kb_search_min_score() -> float:
    """语义检索最低相似度（余弦，0~1）；默认 0.6，设为 0 可关闭过滤。"""
    raw = (os.getenv("KB_SEARCH_MIN_SCORE") or "").strip()
    if not raw:
        return 0.6
    try:
        value = float(raw)
    except ValueError:
        return 0.6
    return max(0.0, min(1.0, value))


DEFAULT_RAG_POLICY = {
    "max_calls": 5,
    "limit": 5,
    "doc_types": [],
    "allow_agentic": True,
    "explore_step_interval": 0,
    "exec_max_rag_calls": 5,
}
