"""索引流水线：parse → chunk → embed → Qdrant。"""
from __future__ import annotations

import json
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.knowledge.index.embeddings import get_embed_model
from app.knowledge.index.qdrant_store import delete_points, upsert_point
from app.knowledge.ingestion.chunkers import chunk_text
from app.knowledge.ingestion.parsers import parse_document_content
from app.models import KnowledgeChunk, KnowledgeDocument, ProjectFeatureTree, TestCase

log = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2)

# 用户主动「重建索引」允许的状态（与前端 canReindex 一致）
REINDEXABLE_STATUSES = frozenset({"active", "draft", "pending_parse"})


REVIEW_DOC_TYPES = frozenset({"standard", "strategy"})


def _upload_requires_review(doc: KnowledgeDocument) -> bool:
    return doc.source_type == "upload" and doc.doc_type in REVIEW_DOC_TYPES


def can_reindex_document(status: str) -> bool:
    return status in REINDEXABLE_STATUSES


def reindex_block_reason(status: str) -> str:
    reasons = {
        "parsing": "文档正在索引中，请稍候（超过 2 分钟可刷新页面后重试）",
        "pending_review": "文档待审核，审核通过后会自动索引",
        "rejected": "文档已驳回，请先修改后提交审核",
        "archived": "文档已归档，无法重建索引",
    }
    return reasons.get(status, "当前状态不支持重建索引")


def _embed_text(text: str) -> list[float] | None:
    model = get_embed_model()
    if model is None:
        return None
    try:
        return model.get_text_embedding(text)
    except Exception:
        log.exception("embedding 失败")
        return None


def _is_stale_parsing(doc: KnowledgeDocument) -> bool:
    """parsing 超过 2 分钟视为上次任务异常中断，允许重跑。"""
    if doc.status != "parsing":
        return False
    if doc.updated_at is None:
        return True
    return doc.updated_at < datetime.utcnow() - timedelta(minutes=2)


def _finalize_doc_status(
    doc: KnowledgeDocument,
    *,
    needs_review: bool,
    ok_any: bool,
    was_published: bool,
) -> None:
    if doc.status != "parsing":
        return
    if needs_review and ok_any:
        doc.status = "pending_review"
    elif ok_any or was_published:
        doc.status = "active"
    else:
        doc.status = "draft"


def run_ingest_document(db: Session, document_id: int) -> bool:
    doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == document_id).first()
    if doc is None:
        return False
    if doc.status in ("pending_review", "rejected", "archived"):
        return False
    if doc.status == "parsing" and not _is_stale_parsing(doc):
        return False
    if doc.status not in REINDEXABLE_STATUSES and doc.status != "parsing":
        return False

    was_published = doc.status == "active"
    doc.status = "parsing"
    db.commit()

    try:
        case: TestCase | None = None
        feature_tree_json: str | None = None
        if doc.doc_type == "case" and doc.source_ref:
            try:
                cid = int(doc.source_ref)
                case = db.query(TestCase).filter(TestCase.id == cid).first()
            except ValueError:
                case = None
        if doc.doc_type == "feature_tree" and doc.source_ref:
            try:
                tid = int(doc.source_ref.replace("tree:", ""))
                tree = db.query(ProjectFeatureTree).filter(ProjectFeatureTree.id == tid).first()
                if tree:
                    feature_tree_json = tree.tree_json
            except ValueError:
                pass

        text = parse_document_content(
            file_path=doc.file_path,
            structured_json=doc.structured_json,
            doc_type=doc.doc_type,
            case=case,
            feature_tree_json=feature_tree_json,
        )
        if not text.strip():
            doc.status = "draft"
            db.commit()
            return False

        old_chunks = db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == doc.id).all()
        old_point_ids = [c.qdrant_point_id for c in old_chunks if c.qdrant_point_id]
        delete_points([p for p in old_point_ids if p])
        for c in old_chunks:
            db.delete(c)
        db.commit()

        pairs = chunk_text(text, doc_type=doc.doc_type)
        needs_review = _upload_requires_review(doc) and not was_published
        indexable = was_published or not _upload_requires_review(doc)
        ok_any = False
        for idx, (section_path, content) in enumerate(pairs):
            chunk = KnowledgeChunk(
                document_id=doc.id,
                chunk_index=idx,
                content=content,
                section_path=section_path,
                embedding_status="pending",
                metadata_json=json.dumps({"doc_type": doc.doc_type}, ensure_ascii=False),
            )
            db.add(chunk)
            db.flush()

            if not indexable:
                chunk.embedding_status = "parsed"
                ok_any = True
                continue

            vec = _embed_text(content)
            if vec is None:
                chunk.embedding_status = "failed"
                continue
            point_id = str(uuid.uuid4())
            payload = {
                "chunk_id": chunk.id,
                "document_id": doc.id,
                "collection_id": doc.collection_id,
                "project_id": doc.project_id,
                "doc_type": doc.doc_type,
                "status": "active",
                "title": doc.title,
                "owner_id": doc.owner_id,
                "modality": "text",
            }
            try:
                upsert_point(point_id=point_id, vector=vec, payload=payload)
                chunk.qdrant_point_id = point_id
                chunk.embedding_status = "indexed"
                ok_any = True
            except Exception:
                log.exception("Qdrant upsert 失败 chunk_id=%s", chunk.id)
                chunk.embedding_status = "failed"

        _finalize_doc_status(doc, needs_review=needs_review, ok_any=ok_any, was_published=was_published)
        db.commit()
        return ok_any
    except Exception:
        log.exception("文档索引失败 document_id=%s", document_id)
        db.rollback()
        doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == document_id).first()
        if doc and doc.status == "parsing":
            doc.status = "pending_parse"
            db.commit()
        return False


def schedule_ingest(document_id: int) -> None:
    from app.database import SessionLocal

    def _job() -> None:
        db = SessionLocal()
        try:
            run_ingest_document(db, document_id)
        finally:
            db.close()

    _executor.submit(_job)


def sync_case_document(db: Session, case: TestCase, collection_id: int) -> None:
    """用例保存时同步到知识库。"""
    source_ref = str(case.id)
    doc = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.collection_id == collection_id,
            KnowledgeDocument.source_ref == source_ref,
            KnowledgeDocument.doc_type == "case",
        )
        .first()
    )
    if doc is None:
        doc = KnowledgeDocument(
            collection_id=collection_id,
            project_id=case.project_id or 0,
            owner_id=case.owner_id,
            doc_type="case",
            source_type="db_sync",
            title=case.title or f"用例 #{case.id}",
            status="active",
            source_ref=source_ref,
        )
        db.add(doc)
        db.flush()
    else:
        doc.title = case.title or doc.title
        doc.project_id = case.project_id or doc.project_id
    db.commit()
    schedule_ingest(doc.id)


def get_or_create_default_collection(db: Session, *, project_id: int, owner_id: int) -> int:
    from app.models import KnowledgeCollection

    row = (
        db.query(KnowledgeCollection)
        .filter(KnowledgeCollection.project_id == project_id, KnowledgeCollection.status == "active")
        .order_by(KnowledgeCollection.id)
        .first()
    )
    if row:
        return row.id
    row = KnowledgeCollection(
        project_id=project_id,
        owner_id=owner_id,
        name="默认知识库",
        description="项目自动创建",
        status="active",
    )
    db.add(row)
    db.flush()
    return row.id
