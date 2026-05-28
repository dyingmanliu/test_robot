"""知识库检索 API：对接 Agent / RAG 前的结构化文本检索。"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.knowledge.chunk_policy import (
    effective_search_min_score,
    has_document_chunk_override,
    normalize_chunk_policy,
    normalize_document_chunk_policy,
    resolve_chunk_policy,
)
from app.knowledge.config import kb_file_storage
from app.knowledge.ingestion.upload_types import validate_upload_path
from app.knowledge.index.pipeline import can_reindex_document, reindex_block_reason, schedule_ingest
from app.knowledge.query.service import knowledge_search
from app.models import (
    KnowledgeCollection,
    KnowledgeDocument,
    Project,
    ProjectKnowledgeSettings,
    RobotInstance,
    RobotInstanceBinding,
    SkillProfile,
    User,
)
from app.rbac import ROLE_PLATFORM_ADMIN, ROLE_TSE, can_view_all_cases
from app.services.company_scope import (
    company_shares_projects_cases,
    enterprise_colleague_user_ids,
    project_readable_by_user,
)
from app.services.knowledge_bootstrap import ensure_skill_profiles
from app.services.knowledge_collection import delete_knowledge_collection
from app.services.knowledge_document import delete_knowledge_document
from app.services.robot_agent_context import resolve_robot_agent_context

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


class CollectionIn(BaseModel):
    name: str
    description: str = ""
    app_bundle_id: str = ""


class CollectionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    app_bundle_id: Optional[str] = None


class CollectionOut(BaseModel):
    id: int
    project_id: int
    name: str
    description: str
    app_bundle_id: str
    status: str
    doc_status_counts: dict[str, int] = Field(default_factory=dict)


class DocumentOut(BaseModel):
    id: int
    collection_id: int
    doc_type: str
    source_type: str
    title: str
    status: str
    version: int
    has_chunk_override: bool = False
    created_at: datetime
    updated_at: datetime


class DocumentChunkPolicyOut(BaseModel):
    use_project_default: bool
    has_document_override: bool
    max_chars: int
    overlap: int
    overlap_short: int
    prefix_title: bool
    prefix_section: bool
    heading_aware: bool
    search_min_score: Optional[float] = None


class DocumentChunkPolicyUpdate(BaseModel):
    use_project_default: bool = True
    max_chars: Optional[int] = Field(None, ge=200, le=4000)
    overlap: Optional[int] = Field(None, ge=0, le=800)
    overlap_short: Optional[int] = Field(None, ge=0, le=400)
    prefix_title: Optional[bool] = None
    prefix_section: Optional[bool] = None
    heading_aware: Optional[bool] = None


class StructuredDocIn(BaseModel):
    collection_id: int
    doc_type: str
    title: str
    structured_json: dict = Field(default_factory=dict)
    use_project_chunk_policy: bool = True
    chunk_policy: Optional[dict] = None


class ReviewIn(BaseModel):
    approve: bool
    note: str = ""


class RobotBindingIn(BaseModel):
    skill_profile_id: Optional[int] = None
    knowledge_collection_ids: list[int] = Field(default_factory=list)
    rag_policy_override: dict = Field(default_factory=dict)


class ChunkPolicyOut(BaseModel):
    max_chars: int
    overlap: int
    overlap_short: int
    prefix_title: bool
    prefix_section: bool
    heading_aware: bool
    search_min_score: Optional[float] = None
    has_project_override: bool = False


class ChunkPolicyUpdate(BaseModel):
    max_chars: Optional[int] = Field(None, ge=200, le=4000)
    overlap: Optional[int] = Field(None, ge=0, le=800)
    overlap_short: Optional[int] = Field(None, ge=0, le=400)
    prefix_title: Optional[bool] = None
    prefix_section: Optional[bool] = None
    heading_aware: Optional[bool] = None
    search_min_score: Optional[float] = Field(None, ge=0.0, le=1.0)


def _require_project(db: Session, user: User, project_id: int) -> Project:
    proj = db.query(Project).filter(Project.id == project_id).first()
    if proj is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not project_readable_by_user(db, user, proj):
        raise HTTPException(status_code=403, detail="无权访问该项目")
    return proj


def _can_review(user: User) -> bool:
    """知识库内容审核由平台管理员负责。"""
    return user.role == ROLE_PLATFORM_ADMIN


def _doc_status_counts_by_collection(
    db: Session, collection_ids: list[int]
) -> dict[int, dict[str, int]]:
    if not collection_ids:
        return {}
    rows = (
        db.query(
            KnowledgeDocument.collection_id,
            KnowledgeDocument.status,
            func.count(),
        )
        .filter(KnowledgeDocument.collection_id.in_(collection_ids))
        .group_by(KnowledgeDocument.collection_id, KnowledgeDocument.status)
        .all()
    )
    out: dict[int, dict[str, int]] = {}
    for cid, st, cnt in rows:
        out.setdefault(int(cid), {})[str(st)] = int(cnt)
    return out


def _collection_out(
    row: KnowledgeCollection,
    *,
    doc_status_counts: dict[str, int] | None = None,
) -> CollectionOut:
    return CollectionOut(
        id=row.id,
        project_id=row.project_id,
        name=row.name,
        description=row.description or "",
        app_bundle_id=row.app_bundle_id or "",
        status=row.status,
        doc_status_counts=doc_status_counts or {},
    )


def _get_collection(
    db: Session,
    *,
    project_id: int,
    collection_id: int,
) -> KnowledgeCollection:
    row = (
        db.query(KnowledgeCollection)
        .filter(
            KnowledgeCollection.id == collection_id,
            KnowledgeCollection.project_id == project_id,
            KnowledgeCollection.status == "active",
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="集合不存在")
    return row


def _require_document(
    db: Session, user: User, project_id: int, doc_id: int
) -> KnowledgeDocument:
    _require_project(db, user, project_id)
    doc = (
        db.query(KnowledgeDocument)
        .filter(KnowledgeDocument.id == doc_id, KnowledgeDocument.project_id == project_id)
        .first()
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return doc


def _document_chunk_policy_out(db: Session, doc: KnowledgeDocument) -> DocumentChunkPolicyOut:
    effective = resolve_chunk_policy(db, doc.project_id, doc.id)
    project_only = resolve_chunk_policy(db, doc.project_id, None)
    has_override = has_document_chunk_override(doc.chunk_policy_json)
    return DocumentChunkPolicyOut(
        use_project_default=not has_override,
        has_document_override=has_override,
        max_chars=int(effective["max_chars"]),
        overlap=int(effective["overlap"]),
        overlap_short=int(effective["overlap_short"]),
        prefix_title=bool(effective.get("prefix_title")),
        prefix_section=bool(effective.get("prefix_section")),
        heading_aware=bool(effective.get("heading_aware")),
        search_min_score=effective_search_min_score(project_only),
    )


def _apply_upload_chunk_policy(
    doc: KnowledgeDocument,
    *,
    use_project_chunk_policy: bool,
    chunk_policy_json: str,
) -> None:
    if use_project_chunk_policy:
        doc.chunk_policy_json = "{}"
        return
    raw = (chunk_policy_json or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="请提供 chunk_policy_json 或选择使用项目默认")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="chunk_policy_json 格式无效") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="chunk_policy_json 须为对象")
    doc.chunk_policy_json = json.dumps(
        normalize_document_chunk_policy(parsed), ensure_ascii=False
    )


def _chunk_policy_out(db: Session, project_id: int) -> ChunkPolicyOut:
    policy = resolve_chunk_policy(db, project_id)
    row = (
        db.query(ProjectKnowledgeSettings)
        .filter(ProjectKnowledgeSettings.project_id == project_id)
        .first()
    )
    has_override = bool(row and (row.chunk_policy_json or "").strip() not in ("", "{}"))
    score = policy.get("search_min_score")
    return ChunkPolicyOut(
        max_chars=int(policy["max_chars"]),
        overlap=int(policy["overlap"]),
        overlap_short=int(policy["overlap_short"]),
        prefix_title=bool(policy.get("prefix_title")),
        prefix_section=bool(policy.get("prefix_section")),
        heading_aware=bool(policy.get("heading_aware")),
        search_min_score=float(score) if score is not None else None,
        has_project_override=has_override,
    )


def _get_or_create_project_knowledge_settings(
    db: Session, project_id: int
) -> ProjectKnowledgeSettings:
    row = (
        db.query(ProjectKnowledgeSettings)
        .filter(ProjectKnowledgeSettings.project_id == project_id)
        .first()
    )
    if row is None:
        row = ProjectKnowledgeSettings(project_id=project_id)
        db.add(row)
        db.flush()
    return row


@router.get("/projects/{project_id}/chunk-policy", response_model=ChunkPolicyOut)
def get_project_chunk_policy(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChunkPolicyOut:
    _require_project(db, user, project_id)
    return _chunk_policy_out(db, project_id)


@router.patch("/projects/{project_id}/chunk-policy", response_model=ChunkPolicyOut)
def update_project_chunk_policy(
    project_id: int,
    body: ChunkPolicyUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChunkPolicyOut:
    _require_project(db, user, project_id)
    row = _get_or_create_project_knowledge_settings(db, project_id)
    current: dict = {}
    if (row.chunk_policy_json or "").strip():
        try:
            parsed = json.loads(row.chunk_policy_json)
            if isinstance(parsed, dict):
                current = parsed
        except json.JSONDecodeError:
            current = {}
    patch = body.model_dump(exclude_unset=True)
    current.update(patch)
    row.chunk_policy_json = json.dumps(normalize_chunk_policy(current), ensure_ascii=False)
    db.commit()
    return _chunk_policy_out(db, project_id)


@router.delete("/projects/{project_id}/chunk-policy", response_model=ChunkPolicyOut)
def reset_project_chunk_policy(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChunkPolicyOut:
    _require_project(db, user, project_id)
    row = (
        db.query(ProjectKnowledgeSettings)
        .filter(ProjectKnowledgeSettings.project_id == project_id)
        .first()
    )
    if row is not None:
        row.chunk_policy_json = "{}"
        db.commit()
    return _chunk_policy_out(db, project_id)


@router.get("/skill-profiles")
def list_skill_profiles(
    catalog_robot_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    ensure_skill_profiles(db)
    q = db.query(SkillProfile)
    if catalog_robot_id:
        q = q.filter(SkillProfile.catalog_robot_id == catalog_robot_id)
    rows = q.order_by(SkillProfile.id).all()
    return {
        "items": [
            {
                "id": r.id,
                "catalog_robot_id": r.catalog_robot_id,
                "name": r.name,
                "skill_names": json.loads(r.skill_names_json or "[]"),
                "is_default": r.is_default,
            }
            for r in rows
        ]
    }


@router.get("/projects/{project_id}/collections", response_model=list[CollectionOut])
def list_collections(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CollectionOut]:
    _require_project(db, user, project_id)
    rows = (
        db.query(KnowledgeCollection)
        .filter(KnowledgeCollection.project_id == project_id, KnowledgeCollection.status == "active")
        .order_by(KnowledgeCollection.id.desc())
        .all()
    )
    counts_map = _doc_status_counts_by_collection(db, [r.id for r in rows])
    return [_collection_out(r, doc_status_counts=counts_map.get(r.id, {})) for r in rows]


@router.post("/projects/{project_id}/collections", response_model=CollectionOut)
def create_collection(
    project_id: int,
    body: CollectionIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CollectionOut:
    proj = _require_project(db, user, project_id)
    row = KnowledgeCollection(
        project_id=project_id,
        owner_id=proj.owner_id,
        name=body.name.strip(),
        description=body.description,
        app_bundle_id=body.app_bundle_id,
        status="active",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _collection_out(row)


@router.patch("/projects/{project_id}/collections/{collection_id}", response_model=CollectionOut)
def update_collection(
    project_id: int,
    collection_id: int,
    body: CollectionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CollectionOut:
    _require_project(db, user, project_id)
    row = _get_collection(db, project_id=project_id, collection_id=collection_id)
    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="名称不能为空")
        row.name = name
    if body.description is not None:
        row.description = body.description
    if body.app_bundle_id is not None:
        row.app_bundle_id = body.app_bundle_id.strip()
    db.commit()
    db.refresh(row)
    return _collection_out(row)


@router.delete("/projects/{project_id}/collections/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection(
    project_id: int,
    collection_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    _require_project(db, user, project_id)
    try:
        delete_knowledge_collection(db, project_id=project_id, collection_id=collection_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/projects/{project_id}/documents", response_model=list[DocumentOut])
def list_documents(
    project_id: int,
    collection_id: Optional[int] = Query(None),
    doc_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DocumentOut]:
    _require_project(db, user, project_id)
    q = db.query(KnowledgeDocument).filter(KnowledgeDocument.project_id == project_id)
    if collection_id is not None:
        q = q.filter(KnowledgeDocument.collection_id == collection_id)
    if doc_type:
        q = q.filter(KnowledgeDocument.doc_type == doc_type)
    rows = q.order_by(KnowledgeDocument.updated_at.desc()).limit(200).all()
    return [
        DocumentOut(
            id=r.id,
            collection_id=r.collection_id,
            doc_type=r.doc_type,
            source_type=r.source_type,
            title=r.title,
            status=r.status,
            version=r.version,
            has_chunk_override=has_document_chunk_override(r.chunk_policy_json),
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]


@router.get(
    "/projects/{project_id}/documents/{doc_id}/chunk-policy",
    response_model=DocumentChunkPolicyOut,
)
def get_document_chunk_policy(
    project_id: int,
    doc_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DocumentChunkPolicyOut:
    doc = _require_document(db, user, project_id, doc_id)
    return _document_chunk_policy_out(db, doc)


@router.patch(
    "/projects/{project_id}/documents/{doc_id}/chunk-policy",
    response_model=DocumentChunkPolicyOut,
)
def update_document_chunk_policy(
    project_id: int,
    doc_id: int,
    body: DocumentChunkPolicyUpdate,
    reindex: bool = Query(False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DocumentChunkPolicyOut:
    doc = _require_document(db, user, project_id, doc_id)
    if body.use_project_default:
        doc.chunk_policy_json = "{}"
    else:
        patch = body.model_dump(exclude_unset=True, exclude={"use_project_default"})
        current: dict = {}
        if has_document_chunk_override(doc.chunk_policy_json):
            try:
                parsed = json.loads(doc.chunk_policy_json)
                if isinstance(parsed, dict):
                    current = parsed
            except json.JSONDecodeError:
                current = {}
        current.update(patch)
        doc.chunk_policy_json = json.dumps(
            normalize_document_chunk_policy(current), ensure_ascii=False
        )
    db.commit()
    db.refresh(doc)
    if reindex:
        if not can_reindex_document(doc.status):
            raise HTTPException(status_code=400, detail=reindex_block_reason(doc.status))
        schedule_ingest(doc.id)
    return _document_chunk_policy_out(db, doc)


@router.post("/projects/{project_id}/documents/upload")
async def upload_document(
    project_id: int,
    collection_id: int = Form(...),
    doc_type: str = Form("standard"),
    title: str = Form(""),
    use_project_chunk_policy: str = Form("true"),
    chunk_policy_json: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    proj = _require_project(db, user, project_id)
    coll = (
        db.query(KnowledgeCollection)
        .filter(KnowledgeCollection.id == collection_id, KnowledgeCollection.project_id == project_id)
        .first()
    )
    if coll is None:
        raise HTTPException(status_code=404, detail="知识库集合不存在")
    storage = kb_file_storage() / str(project_id) / str(collection_id)
    storage.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "upload.bin").name
    dest = storage / f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{safe_name}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        validate_upload_path(dest)
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise
    use_project = use_project_chunk_policy.strip().lower() in ("1", "true", "yes", "on")
    doc = KnowledgeDocument(
        collection_id=collection_id,
        project_id=project_id,
        owner_id=proj.owner_id,
        doc_type=doc_type.strip() or "standard",
        source_type="upload",
        title=(title or safe_name).strip()[:512],
        status="pending_parse",
        file_path=str(dest),
    )
    _apply_upload_chunk_policy(
        doc,
        use_project_chunk_policy=use_project,
        chunk_policy_json=chunk_policy_json,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    schedule_ingest(doc.id)
    return {
        "id": doc.id,
        "status": doc.status,
        "title": doc.title,
        "has_chunk_override": has_document_chunk_override(doc.chunk_policy_json),
    }


@router.post("/projects/{project_id}/documents/structured")
def create_structured_document(
    project_id: int,
    body: StructuredDocIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    proj = _require_project(db, user, project_id)
    coll = (
        db.query(KnowledgeCollection)
        .filter(KnowledgeCollection.id == body.collection_id, KnowledgeCollection.project_id == project_id)
        .first()
    )
    if coll is None:
        raise HTTPException(status_code=404, detail="知识库集合不存在")
    doc = KnowledgeDocument(
        collection_id=body.collection_id,
        project_id=project_id,
        owner_id=proj.owner_id,
        doc_type=body.doc_type,
        source_type="manual_form",
        title=body.title.strip()[:512],
        status="pending_parse",
        structured_json=json.dumps(body.structured_json, ensure_ascii=False),
    )
    if body.use_project_chunk_policy:
        doc.chunk_policy_json = "{}"
    elif body.chunk_policy:
        doc.chunk_policy_json = json.dumps(
            normalize_document_chunk_policy(body.chunk_policy), ensure_ascii=False
        )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    schedule_ingest(doc.id)
    return {
        "id": doc.id,
        "status": doc.status,
        "has_chunk_override": has_document_chunk_override(doc.chunk_policy_json),
    }


@router.delete("/projects/{project_id}/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    project_id: int,
    doc_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    _require_project(db, user, project_id)
    try:
        delete_knowledge_document(db, project_id=project_id, doc_id=doc_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/projects/{project_id}/documents/{doc_id}/submit-review")
def submit_review(
    project_id: int,
    doc_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    _require_project(db, user, project_id)
    doc = (
        db.query(KnowledgeDocument)
        .filter(KnowledgeDocument.id == doc_id, KnowledgeDocument.project_id == project_id)
        .first()
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    if doc.status in ("pending_review", "parsing", "pending_parse"):
        raise HTTPException(status_code=400, detail="文档已在审核或索引流程中")
    if doc.status == "active":
        raise HTTPException(status_code=400, detail="文档已发布，无需重复提交审核")
    doc.status = "pending_review"
    db.commit()
    return {"id": doc.id, "status": doc.status}


@router.post("/documents/{doc_id}/review")
def review_document(
    doc_id: int,
    body: ReviewIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    if not _can_review(user):
        raise HTTPException(status_code=403, detail="需要平台管理员权限")
    doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    if body.approve:
        doc.status = "active"
    else:
        doc.status = "rejected"
    doc.review_note = body.note
    doc.reviewed_by = user.id
    doc.reviewed_at = datetime.utcnow()
    db.commit()
    if body.approve:
        # 须在 commit 之后再调度：后台线程用新 Session，未提交时仍为 pending_review 会直接跳过索引
        schedule_ingest(doc.id)
    return {"id": doc.id, "status": doc.status}


@router.post("/documents/{doc_id}/reindex")
def reindex_document(
    doc_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    if not can_reindex_document(doc.status):
        raise HTTPException(status_code=400, detail=reindex_block_reason(doc.status))
    schedule_ingest(doc.id)
    return {"id": doc.id, "message": "已排队重建索引"}


@router.get("/projects/{project_id}/search")
def search_project_knowledge(
    project_id: int,
    q: str = Query(..., min_length=1),
    collection_id: Optional[int] = Query(None),
    doc_type: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    _require_project(db, user, project_id)
    cids = [collection_id] if collection_id else None
    dtypes = [doc_type] if doc_type else None
    return knowledge_search(
        db,
        query=q,
        collection_ids=cids,
        project_id=project_id,
        doc_types=dtypes,
        limit=limit,
    )


@router.get("/review-queue")
def review_queue(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    if not _can_review(user):
        raise HTTPException(status_code=403, detail="需要平台管理员权限")
    rows = (
        db.query(KnowledgeDocument)
        .filter(KnowledgeDocument.status == "pending_review")
        .order_by(KnowledgeDocument.updated_at.desc())
        .limit(100)
        .all()
    )
    return {
        "items": [
            {
                "id": r.id,
                "project_id": r.project_id,
                "collection_id": r.collection_id,
                "title": r.title,
                "doc_type": r.doc_type,
                "updated_at": r.updated_at.isoformat(),
            }
            for r in rows
        ]
    }


@router.get("/cases/search")
def search_test_cases_kb(
    q: str = Query(..., min_length=1, description="关键词"),
    project_id: Optional[int] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """兼容旧 API：优先语义检索，无向量配置时回退 case_kb LIKE。"""
    from app.services.case_kb import search_cases_kb

    if project_id is not None:
        proj = db.query(Project).filter(Project.id == project_id).first()
        if proj is None:
            return {"items": [], "message": "项目不存在"}
        if not project_readable_by_user(db, user, proj):
            return {"items": [], "message": "无权访问该项目"}

    sem = knowledge_search(
        db, query=q, project_id=project_id, doc_types=["case"], limit=limit
    )
    if sem.get("items"):
        return sem

    if can_view_all_cases(user):
        scope = None
    elif company_shares_projects_cases(db, user):
        scope = enterprise_colleague_user_ids(db, user)
    else:
        scope = [user.id]
    rows = search_cases_kb(db, q=q, project_id=project_id, owner_scope_ids=scope, limit=limit)
    items = []
    for tc, kb in rows:
        snippet = (kb.search_text if kb else "")[:400]
        items.append(
            {
                "case_id": tc.id,
                "project_id": tc.project_id,
                "title": tc.title,
                "priority": tc.priority,
                "revision_no": tc.revision_no,
                "snippet": snippet,
            }
        )
    return {"items": items, "query": q}


@router.get("/robot-instances/{instance_id}/knowledge-binding")
def get_robot_knowledge_binding(
    instance_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    inst = db.query(RobotInstance).filter(RobotInstance.id == instance_id).first()
    if inst is None:
        raise HTTPException(status_code=404, detail="机器人实例不存在")
    if inst.user_id != user.id and user.role not in (ROLE_PLATFORM_ADMIN, ROLE_TSE):
        raise HTTPException(status_code=403, detail="无权查看该实例")
    try:
        return resolve_robot_agent_context(db, robot_instance_id=instance_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.patch("/robot-instances/{instance_id}/knowledge-binding")
def patch_robot_knowledge_binding(
    instance_id: int,
    body: RobotBindingIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    inst = db.query(RobotInstance).filter(RobotInstance.id == instance_id).first()
    if inst is None:
        raise HTTPException(status_code=404, detail="机器人实例不存在")
    if inst.user_id != user.id and user.role not in (ROLE_PLATFORM_ADMIN, ROLE_TSE):
        raise HTTPException(status_code=403, detail="无权修改该实例")
    row = (
        db.query(RobotInstanceBinding)
        .filter(RobotInstanceBinding.robot_instance_id == instance_id)
        .first()
    )
    if row is None:
        row = RobotInstanceBinding(robot_instance_id=instance_id)
        db.add(row)
    row.skill_profile_id = body.skill_profile_id
    row.knowledge_collection_ids_json = json.dumps(body.knowledge_collection_ids, ensure_ascii=False)
    row.rag_policy_override_json = json.dumps(body.rag_policy_override, ensure_ascii=False)
    db.commit()
    ctx = resolve_robot_agent_context(db, robot_instance_id=instance_id)
    return ctx
