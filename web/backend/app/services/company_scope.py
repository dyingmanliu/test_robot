"""公司维度：同事用户 ID、项目/用例可见范围、租用机器人实例可用性。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Company, Project, RobotInstance, TestCase, TestRun, User
from app.rbac import ROLE_ENTERPRISE, can_view_all_cases


def enterprise_colleague_user_ids(db: Session, user: User) -> list[int]:
    if user.company_id is None:
        return [user.id]
    rows = db.query(User.id).filter(User.company_id == user.company_id).all()
    return [int(r[0]) for r in rows]


def company_shares_projects_cases(db: Session, user: User) -> bool:
    if can_view_all_cases(user):
        return True
    if user.role != ROLE_ENTERPRISE or user.company_id is None:
        return False
    c = db.query(Company).filter(Company.id == user.company_id).first()
    return bool(c and c.share_projects_cases_internally)


def case_scope_query(db: Session, query, user: User):
    if can_view_all_cases(user):
        return query
    if company_shares_projects_cases(db, user):
        return query.filter(TestCase.owner_id.in_(enterprise_colleague_user_ids(db, user)))
    return query.filter(TestCase.owner_id == user.id)


def project_scope_query(db: Session, query, user: User):
    if can_view_all_cases(user):
        return query
    if company_shares_projects_cases(db, user):
        return query.filter(Project.owner_id.in_(enterprise_colleague_user_ids(db, user)))
    return query.filter(Project.owner_id == user.id)


def project_readable_by_user(db: Session, user: User, proj: Project | None) -> bool:
    if proj is None:
        return False
    if can_view_all_cases(user):
        return True
    if proj.owner_id == user.id:
        return True
    if not company_shares_projects_cases(db, user):
        return False
    owner_cid = db.query(User.company_id).filter(User.id == proj.owner_id).scalar()
    return bool(user.company_id and owner_cid == user.company_id)


def project_owned_by_user(user: User, proj: Project | None) -> bool:
    if proj is None:
        return False
    if can_view_all_cases(user):
        return True
    return proj.owner_id == user.id


def run_scope_query(db: Session, user: User):
    q = db.query(TestRun)
    if can_view_all_cases(user):
        return q
    if company_shares_projects_cases(db, user):
        return q.filter(TestRun.owner_id.in_(enterprise_colleague_user_ids(db, user)))
    return q.filter(TestRun.owner_id == user.id)


def can_use_robot_instance(db: Session, user: User, inst: RobotInstance) -> bool:
    if inst.status != "active":
        return False
    if user.company_id and inst.company_id is not None and inst.company_id == user.company_id:
        return True
    if inst.user_id == user.id:
        return True
    return False
