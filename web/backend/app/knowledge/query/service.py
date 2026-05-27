"""语义检索服务。"""
from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy.orm import Session

from app.knowledge.config import DEFAULT_RAG_POLICY
from app.knowledge.index.embeddings import format_embedding_error, get_embed_model
from app.knowledge.index.qdrant_store import search_vectors
from app.models import KnowledgeChunk, KnowledgeDocument

log = logging.getLogger(__name__)


def knowledge_search(
    db: Session,
    *,
    query: str,
    collection_ids: list[int] | None = None,
    project_id: int | None = None,
    doc_types: list[str] | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {"items": [], "query": q}
    t0 = time.perf_counter()
    model = get_embed_model()
    if model is None:
        return {"items": [], "query": q, "error": "embedding 未配置"}
    try:
        vec = model.get_text_embedding(q)
    except Exception as exc:
        log.warning("query embedding 失败: %s", exc)
        return {"items": [], "query": q, "error": format_embedding_error(exc)}
    hits = search_vectors(
        query_vector=vec,
        limit=limit,
        collection_ids=collection_ids,
        project_id=project_id,
        doc_types=doc_types or None,
    )
    items: list[dict[str, Any]] = []
    for h in hits:
        cid = h.get("chunk_id")
        if cid is None:
            continue
        chunk = db.query(KnowledgeChunk).filter(KnowledgeChunk.id == cid).first()
        if chunk is None:
            continue
        doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == chunk.document_id).first()
        items.append(
            {
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "collection_id": h.get("collection_id"),
                "doc_type": h.get("doc_type") or (doc.doc_type if doc else ""),
                "title": h.get("title") or (doc.title if doc else ""),
                "score": h.get("score"),
                "snippet": (chunk.content or "")[:600],
                "section_path": chunk.section_path,
            }
        )
    return {
        "items": items,
        "query": q,
        "latency_ms": int((time.perf_counter() - t0) * 1000),
    }


def merge_rag_policy(base: dict | None, override: dict | None) -> dict:
    out = dict(DEFAULT_RAG_POLICY)
    if base:
        out.update(base)
    if override:
        out.update(override)
    return out
