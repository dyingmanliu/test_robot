"""Qdrant 向量库封装。"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.knowledge.config import qdrant_collection, qdrant_url


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    return QdrantClient(url=qdrant_url(), timeout=30)


def ensure_collection(vector_size: int = 1024) -> None:
    client = get_qdrant_client()
    name = qdrant_collection()
    if client.collection_exists(name):
        return
    client.create_collection(
        collection_name=name,
        vectors_config=qmodels.VectorParams(size=vector_size, distance=qmodels.Distance.COSINE),
    )


def upsert_point(*, point_id: str, vector: list[float], payload: dict[str, Any]) -> None:
    ensure_collection(len(vector))
    client = get_qdrant_client()
    client.upsert(
        collection_name=qdrant_collection(),
        points=[qmodels.PointStruct(id=point_id, vector=vector, payload=payload)],
    )


def delete_points(point_ids: list[str]) -> None:
    if not point_ids:
        return
    client = get_qdrant_client()
    if not client.collection_exists(qdrant_collection()):
        return
    client.delete(
        collection_name=qdrant_collection(),
        points_selector=qmodels.PointIdsList(points=point_ids),
    )


def search_vectors(
    *,
    query_vector: list[float],
    limit: int = 5,
    collection_ids: list[int] | None = None,
    project_id: int | None = None,
    doc_types: list[str] | None = None,
) -> list[dict[str, Any]]:
    ensure_collection(len(query_vector))
    client = get_qdrant_client()
    must: list[qmodels.FieldCondition] = [
        qmodels.FieldCondition(key="status", match=qmodels.MatchValue(value="active")),
    ]
    if collection_ids:
        must.append(
            qmodels.FieldCondition(
                key="collection_id",
                match=qmodels.MatchAny(any=collection_ids),
            )
        )
    if project_id is not None:
        must.append(
            qmodels.FieldCondition(key="project_id", match=qmodels.MatchValue(value=project_id))
        )
    if doc_types:
        must.append(
            qmodels.FieldCondition(key="doc_type", match=qmodels.MatchAny(any=doc_types))
        )
    flt = qmodels.Filter(must=must)
    resp = client.query_points(
        collection_name=qdrant_collection(),
        query=query_vector,
        query_filter=flt,
        limit=limit,
        with_payload=True,
    )
    points = resp.points or []
    out: list[dict[str, Any]] = []
    for h in points:
        payload = h.payload or {}
        out.append(
            {
                "score": float(h.score or 0),
                "chunk_id": payload.get("chunk_id"),
                "document_id": payload.get("document_id"),
                "collection_id": payload.get("collection_id"),
                "doc_type": payload.get("doc_type"),
                "title": payload.get("title"),
            }
        )
    return out
