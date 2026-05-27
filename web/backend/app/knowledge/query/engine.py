"""LlamaIndex QueryEngine 薄封装（向量检索委托 query/service）。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.knowledge.query.service import knowledge_search


def query_engine_search(
    db: Session,
    *,
    query: str,
    collection_ids: list[int] | None,
    project_id: int | None,
    doc_types: list[str] | None,
    limit: int,
) -> dict:
    return knowledge_search(
        db,
        query=query,
        collection_ids=collection_ids,
        project_id=project_id,
        doc_types=doc_types,
        limit=limit,
    )
