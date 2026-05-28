"""用例 / 功能树 → 知识库同步。"""
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.knowledge.index.pipeline import get_or_create_default_collection, sync_case_document
from app.models import (
    KnowledgeDocument,
    ProjectFeatureAnalysisRun,
    ProjectFeatureTree,
    TestCase,
)
from app.knowledge.index.pipeline import schedule_ingest


def sync_test_case_to_knowledge(db: Session, case: TestCase) -> None:
    if case.project_id is None:
        return
    coll_id = get_or_create_default_collection(db, project_id=case.project_id, owner_id=case.owner_id)
    sync_case_document(db, case, coll_id)


def _feature_tree_knowledge_title(db: Session, tree: ProjectFeatureTree) -> str:
    """知识库文档标题：优先版本标签；旧版纯 vN 时补上应用名便于识别。"""
    label = (tree.version_label or "").strip()
    run = (
        db.query(ProjectFeatureAnalysisRun)
        .filter(ProjectFeatureAnalysisRun.id == tree.run_id)
        .first()
    )
    app = ""
    if run is not None:
        app = (run.app_display_name or run.bundle_id or "").strip()
    if label and not re.match(r"^v\d+$", label, re.IGNORECASE):
        return label[:512]
    if label and app:
        return f"{app}-{label}"[:512]
    if label:
        return label[:512]
    if app:
        return f"{app} 功能树"[:512]
    return f"功能树 #{tree.id}"


def sync_feature_tree_to_knowledge(db: Session, tree: ProjectFeatureTree) -> None:
    coll_id = get_or_create_default_collection(
        db, project_id=tree.project_id, owner_id=tree.owner_id
    )
    source_ref = f"tree:{tree.id}"
    title = _feature_tree_knowledge_title(db, tree)
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
            title=title,
            status="active",
            source_ref=source_ref,
            structured_json=tree.tree_json,
        )
        db.add(doc)
    else:
        doc.structured_json = tree.tree_json
        doc.title = title
        doc.status = "active"
    db.commit()
    schedule_ingest(doc.id)
