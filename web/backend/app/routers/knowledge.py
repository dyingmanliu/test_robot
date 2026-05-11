"""知识库检索 API：对接 Agent / RAG 前的结构化文本检索。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Project, User
from app.rbac import can_view_all_cases
from app.services.case_kb import search_cases_kb

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/cases/search")
def search_test_cases_kb(
    q: str = Query(..., min_length=1, description="关键词"),
    project_id: Optional[int] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    if project_id is not None:
        proj = db.query(Project).filter(Project.id == project_id).first()
        if proj is None:
            return {"items": [], "message": "项目不存在"}
        if not can_view_all_cases(user) and proj.owner_id != user.id:
            return {"items": [], "message": "无权访问该项目"}

    scope = None if can_view_all_cases(user) else [user.id]
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
