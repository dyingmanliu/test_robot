"""数据看板（按 RBAC 区分全量与租户范围）。"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Project, TestCase, TestRun, User
from app.rbac import can_view_all_cases
from app.services.run_metrics import count_recognition_steps

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _runs_rows(db: Session, user: User):
    q = db.query(TestRun.status, TestRun.step_log)
    if not can_view_all_cases(user):
        q = q.filter(TestRun.owner_id == user.id)
    return q.all()


def _cases_query(db: Session, user: User):
    q = db.query(TestCase)
    if not can_view_all_cases(user):
        q = q.filter(TestCase.owner_id == user.id)
    return q


@router.get("/summary")
def dashboard_summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    if can_view_all_cases(user):
        base = {
            "scope": "global",
            "role": user.role,
            "projects": db.query(Project).count(),
            "test_cases": db.query(TestCase).count(),
            "test_runs": db.query(TestRun).count(),
        }
    else:
        base = {
            "scope": "tenant",
            "role": user.role,
            "projects": db.query(Project).filter(Project.owner_id == user.id).count(),
            "test_cases": db.query(TestCase).filter(TestCase.owner_id == user.id).count(),
            "test_runs": db.query(TestRun).filter(TestRun.owner_id == user.id).count(),
        }

    run_rows = _runs_rows(db, user)
    status_ct = Counter(s for s, _ in run_rows)
    total_steps = sum(count_recognition_steps(sl) for _, sl in run_rows)

    tc_scope = _cases_query(db, user)
    seven_ago = datetime.utcnow() - timedelta(days=7)
    cases_updated_7d = tc_scope.filter(TestCase.updated_at >= seven_ago).count()

    prio_rows = (
        tc_scope.with_entities(TestCase.priority, func.count(TestCase.id)).group_by(TestCase.priority).all()
    )
    cases_by_priority = {str(p or "—"): int(n) for p, n in prio_rows}

    base["runs_success"] = status_ct.get("success", 0)
    base["runs_failed"] = status_ct.get("failed", 0)
    base["runs_cancelled"] = status_ct.get("cancelled", 0)
    base["runs_pending_or_running"] = status_ct.get("pending", 0) + status_ct.get("running", 0)
    base["total_recognition_steps"] = total_steps
    base["cases_by_priority"] = cases_by_priority
    base["cases_updated_last_7_days"] = cases_updated_7d
    return base
