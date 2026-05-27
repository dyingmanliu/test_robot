"""知识库文档删除：清理 Qdrant 向量、切片与上传文件。"""
from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.knowledge.index.qdrant_store import delete_points
from app.models import KnowledgeChunk, KnowledgeDocument

log = logging.getLogger(__name__)


def delete_knowledge_document(
    db: Session,
    *,
    project_id: int,
    doc_id: int,
) -> None:
    doc = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.id == doc_id,
            KnowledgeDocument.project_id == project_id,
        )
        .first()
    )
    if doc is None:
        raise ValueError("文档不存在")

    point_ids = [
        r[0]
        for r in db.query(KnowledgeChunk.qdrant_point_id)
        .filter(
            KnowledgeChunk.document_id == doc_id,
            KnowledgeChunk.qdrant_point_id.isnot(None),
        )
        .all()
        if r[0]
    ]
    if point_ids:
        try:
            delete_points(point_ids)
        except Exception:
            log.exception("删除 Qdrant 向量失败 document_id=%s", doc_id)

    if doc.file_path:
        try:
            Path(doc.file_path).unlink(missing_ok=True)
        except OSError:
            log.exception("删除知识库文件失败 %s", doc.file_path)

    db.delete(doc)
    db.commit()
