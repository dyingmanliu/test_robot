"""用例 / 功能树 → 知识库同步。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.knowledge.index.pipeline import get_or_create_default_collection, sync_case_document
from app.models import KnowledgeCollection, KnowledgeDocument, ProjectFeatureTree, TestCase
from app.knowledge.index.pipeline import schedule_ingest


def sync_test_case_to_knowledge(db: Session, case: TestCase) -> None:
    if case.project_id is None:
        return
    coll_id = get_or_create_default_collection(db, project_id=case.project_id, owner_id=case.owner_id)
    sync_case_document(db, case, coll_id)


def sync_feature_tree_to_knowledge(db: Session, tree: ProjectFeatureTree) -> None:
    from app.models import KnowledgeDocument

    coll_id = get_or_create_default_collection(
        db, project_id=tree.project_id, owner_id=tree.owner_id
    )
    source_ref = f"tree:{tree.id}"
    doc = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.collection_id == coll_id,
            KnowledgeDocument.source_ref == source_ref,
            KnowledgeDocument.doc_type == "feature_tree",
        )
        .first()
    )
    if doc is None:
        doc = KnowledgeDocument(
            collection_id=coll_id,
            project_id=tree.project_id,
            owner_id=tree.owner_id,
            doc_type="feature_tree",
            source_type="agent_generated",
            title=tree.version_label or f"功能树 #{tree.id}",
            status="active",
            source_ref=source_ref,
            structured_json=tree.tree_json,
        )
        db.add(doc)
    else:
        doc.structured_json = tree.tree_json
        doc.title = tree.version_label or doc.title
        doc.status = "active"
    db.commit()
    schedule_ingest(doc.id)
