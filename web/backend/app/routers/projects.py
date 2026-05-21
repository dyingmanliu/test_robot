"""项目空间（多租户隔离）：被测应用、测试目标与用例聚合容器。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Project, ProjectFeatureTree, TestCase, TestRun, User
from app.rbac import can_view_all_cases
from app.schemas import ProjectCreate, ProjectOut, ProjectUpdate, ProjectWithStatsOut
from app.services.company_scope import project_owned_by_user, project_scope_query
from app.services.project_dashboard import build_project_dashboard_payload

router = APIRouter(prefix="/projects", tags=["projects"])


def _get_project_readable(db: Session, project_id: int, user: User) -> Project | None:
    q = project_scope_query(db, db.query(Project).filter(Project.id == project_id), user)
    return q.first()


def _get_project_owned(db: Session, project_id: int, user: User) -> Project | None:
    p = db.query(Project).filter(Project.id == project_id).first()
    if p is None or not project_owned_by_user(user, p):
        return None
    return p


def _require_project(db: Session, project_id: int, user: User) -> Project:
    """读权限：本人项目或（公司开启内部共享时）同事项目。"""
    p = _get_project_readable(db, project_id, user)
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目空间不存在或无权访问")
    return p


def _require_project_owner(db: Session, project_id: int, user: User) -> Project:
    """写权限：仅项目归属人或平台/TSE。"""
    p = _get_project_owned(db, project_id, user)
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目空间不存在或无权修改")
    return p


@router.get("", response_model=list[ProjectWithStatsOut])
def list_projects(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ProjectWithStatsOut]:
    q = project_scope_query(db, db.query(Project), user)
    projects = q.order_by(desc(Project.updated_at)).all()
    ids = [p.id for p in projects]
    counts: dict[int, int] = {}
    if ids:
        rows = (
            db.query(TestCase.project_id, func.count(TestCase.id))
            .filter(TestCase.project_id.in_(ids))
            .group_by(TestCase.project_id)
            .all()
        )
        counts = {int(pid): int(n) for pid, n in rows if pid is not None}
    tree_counts: dict[int, int] = {}
    if ids:
        trows = (
            db.query(ProjectFeatureTree.project_id, func.count(ProjectFeatureTree.id))
            .filter(ProjectFeatureTree.project_id.in_(ids))
            .group_by(ProjectFeatureTree.project_id)
            .all()
        )
        tree_counts = {int(pid): int(n) for pid, n in trows if pid is not None}
    return [
        ProjectWithStatsOut(
            id=p.id,
            owner_id=p.owner_id,
            name=p.name,
            tested_app_name=p.tested_app_name,
            test_objective=p.test_objective,
            created_at=p.created_at,
            updated_at=p.updated_at,
            test_case_count=counts.get(p.id, 0),
            confirmed_feature_tree_count=tree_counts.get(p.id, 0),
        )
        for p in projects
    ]


@router.post("", response_model=ProjectOut)
def create_project(
    body: ProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Project:
    # 企业用户仅能为自己租户创建；TSE/管理员可为任意租户代建时仍需指定归属——此处简化为仅自建
    p = Project(
        owner_id=user.id,
        name=body.name.strip(),
        tested_app_name=body.tested_app_name.strip(),
        test_objective=(body.test_objective or "").strip(),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.get("/{project_id}/dashboard")
def project_dashboard(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """项目独立看板：聚合执行任务数、最新报告摘要、活跃机器人、缺陷趋势（数据服务聚合）。"""
    _require_project(db, project_id, user)
    return build_project_dashboard_payload(db, project_id)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Project:
    return _require_project(db, project_id, user)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int,
    body: ProjectUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Project:
    p = _require_project_owner(db, project_id, user)
    data = body.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        p.name = data["name"].strip()
    if "tested_app_name" in data and data["tested_app_name"] is not None:
        p.tested_app_name = data["tested_app_name"].strip()
    if "test_objective" in data:
        p.test_objective = (data["test_objective"] or "").strip()
    db.commit()
    db.refresh(p)
    return p


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    p = _get_project_owned(db, project_id, user)
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目空间不存在或无权访问")
    n = db.query(TestCase).filter(TestCase.project_id == project_id).count()
    if n > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="项目下仍有用例，请先删除或迁移用例后再删除项目空间",
        )
    db.delete(p)
    db.commit()


@router.get("/{project_id}/reports")
def project_reports_stub(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """测试报告聚合（占位）：接入报告服务后按项目空间返回。"""
    _require_project(db, project_id, user)
    return {"project_id": project_id, "items": [], "message": "报告服务占位：按项目空间聚合展示"}


@router.get("/{project_id}/task-summary")
def project_task_summary(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """任务与执行摘要（占位聚合）：按项目统计用例数与运行次数。"""
    _require_project(db, project_id, user)
    case_n = db.query(TestCase).filter(TestCase.project_id == project_id).count()
    run_n = (
        db.query(TestRun)
        .join(TestCase, TestRun.case_id == TestCase.id)
        .filter(TestCase.project_id == project_id)
        .count()
    )
    return {
        "project_id": project_id,
        "test_cases": case_n,
        "test_runs": run_n,
        "message": "任务/报告容器：与用例、执行记录联动",
    }
