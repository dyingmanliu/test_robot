"""知识集合删除：清理 Qdrant 向量、文件存储与机器人绑定。"""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from app.knowledge.config import kb_file_storage
from app.knowledge.index.qdrant_store import delete_points
from app.models import KnowledgeChunk, KnowledgeCollection, KnowledgeDocument, RobotInstanceBinding

log = logging.getLogger(__name__)


def _remove_collection_from_bindings(db: Session, collection_id: int) -> None:
    rows = db.query(RobotInstanceBinding).all()
    for row in rows:
        try:
            ids = [int(x) for x in json.loads(row.knowledge_collection_ids_json or "[]") if str(x).isdigit()]
        except json.JSONDecodeError:
            continue
        if collection_id not in ids:
            continue
        row.knowledge_collection_ids_json = json.dumps(
            [x for x in ids if int(x) != collection_id],
            ensure_ascii=False,
        )


def delete_knowledge_collection(
    db: Session,
    *,
    project_id: int,
    collection_id: int,
) -> None:
    coll = (
        db.query(KnowledgeCollection)
        .filter(
            KnowledgeCollection.id == collection_id,
            KnowledgeCollection.project_id == project_id,
        )
        .first()
    )
    if coll is None:
        raise ValueError("集合不存在")

    doc_ids = [
        r[0]
        for r in db.query(KnowledgeDocument.id)
        .filter(KnowledgeDocument.collection_id == collection_id)
        .all()
    ]
    if doc_ids:
        point_ids = [
            r[0]
            for r in db.query(KnowledgeChunk.qdrant_point_id)
            .filter(
                KnowledgeChunk.document_id.in_(doc_ids),
                KnowledgeChunk.qdrant_point_id.isnot(None),
            )
            .all()
            if r[0]
        ]
        try:
            delete_points(point_ids)
        except Exception:
            log.exception("删除 Qdrant 向量失败 collection_id=%s", collection_id)

    storage_dir: Path = kb_file_storage() / str(project_id) / str(collection_id)
    if storage_dir.exists():
        try:
            shutil.rmtree(storage_dir)
        except OSError:
            log.exception("删除知识库文件目录失败 %s", storage_dir)

    _remove_collection_from_bindings(db, collection_id)
    db.delete(coll)
    db.commit()
