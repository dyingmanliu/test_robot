"""agent_service 内部知识库检索（service token，无用户 JWT）。"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.knowledge.query.service import knowledge_search
from app.models import Project
from app.services.case_kb import search_cases_kb
from app.services.robot_agent_context import resolve_robot_agent_context

router = APIRouter(prefix="/internal", tags=["internal"])


def _verify_service_token(authorization: str | None = Header(None)) -> None:
    expected = (os.getenv("WEB_SERVICE_TOKEN") or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="WEB_SERVICE_TOKEN 未配置")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少 service token")
    token = authorization[7:].strip()
    if token != expected:
        raise HTTPException(status_code=403, detail="无效的 service token")


class KnowledgeQueryRequest(BaseModel):
    robot_instance_id: int | None = None
    query: str
    doc_types: list[str] = Field(default_factory=list)
    limit: int = 5
    project_id: int | None = None
    owner_scope_ids: str | None = None


@router.get("/knowledge/cases/search")
def internal_search_cases_kb(
    q: str = Query(..., min_length=1),
    project_id: Optional[int] = Query(None),
    owner_scope_ids: Optional[str] = Query(
        None,
        description="逗号分隔的 owner_id 列表；省略表示不限 owner",
    ),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: None = Depends(_verify_service_token),
) -> dict:
    if project_id is not None:
        proj = db.query(Project).filter(Project.id == project_id).first()
        if proj is None:
            return {"items": [], "message": "项目不存在"}

    sem = knowledge_search(db, query=q, project_id=project_id, doc_types=["case"], limit=limit)
    if sem.get("items"):
        return sem

    scope: list[int] | None = None
    if owner_scope_ids:
        try:
            scope = [int(x.strip()) for x in owner_scope_ids.split(",") if x.strip()]
        except ValueError as e:
            raise HTTPException(status_code=422, detail="owner_scope_ids 格式无效") from e

    rows = search_cases_kb(db, q=q, project_id=project_id, owner_scope_ids=scope, limit=limit)
    items = []
    for tc, kb in rows:
        snippet = (kb.search_text if kb else "") or ""
        items.append(
            {
                "case_id": tc.id,
                "project_id": tc.project_id,
                "title": tc.title,
                "priority": tc.priority,
                "revision_no": tc.revision_no,
                "snippet": snippet[:600],
            }
        )
    return {"items": items, "query": q}


@router.post("/knowledge/query")
def internal_knowledge_query(
    body: KnowledgeQueryRequest,
    db: Session = Depends(get_db),
    _: None = Depends(_verify_service_token),
) -> dict:
    collection_ids: list[int] | None = None
    limit = body.limit
    if body.robot_instance_id is not None:
        scope: list[int] | None = None
        if body.owner_scope_ids:
            scope = [int(x.strip()) for x in body.owner_scope_ids.split(",") if x.strip()]
        ctx = resolve_robot_agent_context(
            db,
            robot_instance_id=body.robot_instance_id,
            project_id=body.project_id,
            owner_scope_ids=scope,
        )
        collection_ids = ctx.get("knowledge_collection_ids") or None
        if not collection_ids:
            collection_ids = None
        limit = min(limit, int(ctx.get("rag_policy", {}).get("limit", limit)))
    return knowledge_search(
        db,
        query=body.query,
        collection_ids=collection_ids,
        project_id=body.project_id,
        doc_types=body.doc_types or None,
        limit=limit,
    )


@router.get("/robots/{robot_instance_id}/agent-context")
def internal_robot_agent_context(
    robot_instance_id: int,
    project_id: Optional[int] = Query(None),
    owner_scope_ids: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: None = Depends(_verify_service_token),
) -> dict:
    scope: list[int] | None = None
    if owner_scope_ids:
        scope = [int(x.strip()) for x in owner_scope_ids.split(",") if x.strip()]
    try:
        return resolve_robot_agent_context(
            db,
            robot_instance_id=robot_instance_id,
            project_id=project_id,
            owner_scope_ids=scope,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
