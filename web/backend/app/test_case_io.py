"""测试用例 API：ORM ↔ Pydantic（步骤 JSON）。"""

from __future__ import annotations

import json

from app.models import TestCase, TestCaseRevision
from app.schemas import CaseStepJson, TestCaseOut, TestCaseRevisionOut


def _steps_from_raw(raw: str | None) -> list[CaseStepJson]:
    if not raw or not str(raw).strip():
        return []
    try:
        data = json.loads(raw)
        if not isinstance(data, list):
            return []
        out: list[CaseStepJson] = []
        for i, item in enumerate(data, start=1):
            if not isinstance(item, dict):
                continue
            out.append(
                CaseStepJson(
                    order=int(item.get("order", i)),
                    description=str(item.get("description", "")),
                    expected=str(item.get("expected", "")),
                )
            )
        return out
    except (json.JSONDecodeError, TypeError, ValueError):
        return []


def steps_to_json(steps: list[CaseStepJson]) -> str:
    return json.dumps([s.model_dump() for s in steps], ensure_ascii=False)


def test_case_to_out(tc: TestCase) -> TestCaseOut:
    return TestCaseOut(
        id=tc.id,
        owner_id=tc.owner_id,
        project_id=tc.project_id,
        title=tc.title,
        task_text=tc.task_text,
        preconditions=tc.preconditions or "",
        steps=_steps_from_raw(tc.steps_json),
        case_format=getattr(tc, "case_format", None) or "structured",
        case_yaml=getattr(tc, "case_yaml", None) or "",
        priority=tc.priority or "P2",
        revision_no=tc.revision_no or 1,
        created_at=tc.created_at,
        updated_at=tc.updated_at,
    )


def revision_to_out(row: TestCaseRevision) -> TestCaseRevisionOut:
    return TestCaseRevisionOut(
        id=row.id,
        case_id=row.case_id,
        revision_no=row.revision_no,
        title=row.title,
        task_text=row.task_text,
        preconditions=row.preconditions or "",
        steps=_steps_from_raw(row.steps_json),
        case_format=getattr(row, "case_format", None) or "structured",
        case_yaml=getattr(row, "case_yaml", None) or "",
        priority=row.priority or "P2",
        created_at=row.created_at,
    )
