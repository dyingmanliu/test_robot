"""用例知识库：扁平检索文本，供 Agent / RAG 层检索（本地为 LIKE，可换向量库）。"""

from __future__ import annotations

import json
import logging
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import CaseKbDocument, TestCase

log = logging.getLogger(__name__)


def build_kb_search_blob(case: TestCase) -> str:
    parts: list[str] = [
        case.title or "",
        case.task_text or "",
        getattr(case, "preconditions", "") or "",
        getattr(case, "priority", "") or "",
    ]
    raw = getattr(case, "steps_json", None) or "[]"
    try:
        steps = json.loads(raw)
        if isinstance(steps, list):
            for s in steps:
                if isinstance(s, dict):
                    parts.append(str(s.get("description", "")))
                    parts.append(str(s.get("expected", "")))
    except json.JSONDecodeError:
        parts.append(raw)
    return "\n".join(p for p in parts if p)


def upsert_case_kb(db: Session, case: TestCase) -> None:
    body = build_kb_search_blob(case)
    row = db.query(CaseKbDocument).filter(CaseKbDocument.case_id == case.id).first()
    if row is None:
        db.add(CaseKbDocument(case_id=case.id, search_text=body))
    else:
        row.search_text = body


def search_cases_kb(
    db: Session,
    *,
    q: str,
    project_id: Optional[int],
    owner_scope_ids: Optional[list[int]],
    limit: int = 20,
) -> list[tuple[TestCase, Optional[CaseKbDocument]]]:
    """简单包含匹配；后续可替换为向量检索。"""
    term = (q or "").strip()
    if not term:
        return []

    qq = db.query(TestCase, CaseKbDocument).outerjoin(
        CaseKbDocument, CaseKbDocument.case_id == TestCase.id
    )
    if project_id is not None:
        qq = qq.filter(TestCase.project_id == project_id)
    if owner_scope_ids is not None:
        qq = qq.filter(TestCase.owner_id.in_(owner_scope_ids))

    like = f"%{term}%"
    qq = qq.filter(
        or_(
            TestCase.title.ilike(like),
            TestCase.task_text.ilike(like),
            CaseKbDocument.search_text.ilike(like),
        )
    )
    rows = qq.order_by(TestCase.updated_at.desc()).limit(limit).all()
    return [(t, kb) for t, kb in rows]
