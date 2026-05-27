"""agent_service 内部知识库检索（service token，无用户 JWT）。"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Project
from app.services.case_kb import search_cases_kb

router = APIRouter(prefix="/internal/knowledge", tags=["internal-knowledge"])


def _verify_service_token(authorization: str | None = Header(None)) -> None:
    expected = (os.getenv("WEB_SERVICE_TOKEN") or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="WEB_SERVICE_TOKEN 未配置")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少 service token")
    token = authorization[7:].strip()
    if token != expected:
        raise HTTPException(status_code=403, detail="无效的 service token")


@router.get("/cases/search")
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
