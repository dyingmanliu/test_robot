"""内置 RBAC：预定义角色与数据范围辅助函数。

网关可校验 JWT `role` 声明；服务内以数据库 `users.role` 为准并做一次一致性提示。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import TestCase, TestRun, User

# 预定义角色（写入 JWT 与数据库）
ROLE_PLATFORM_ADMIN = "platform_admin"
ROLE_TSE = "tse"
ROLE_ENTERPRISE = "enterprise"

ROLES: tuple[str, ...] = (ROLE_PLATFORM_ADMIN, ROLE_TSE, ROLE_ENTERPRISE)

ROLE_LABELS: dict[str, str] = {
    ROLE_PLATFORM_ADMIN: "平台管理员",
    ROLE_TSE: "内部测试工程师（TSE）",
    ROLE_ENTERPRISE: "外部企业用户",
}


def can_view_all_cases(user: User) -> bool:
    return user.role in (ROLE_PLATFORM_ADMIN, ROLE_TSE)


def can_manage_users(user: User) -> bool:
    return user.role == ROLE_PLATFORM_ADMIN


def case_scope_filter(query, user: User):
    """测试用例列表/查询：企业用户仅本人空间。"""
    if can_view_all_cases(user):
        return query
    return query.filter(TestCase.owner_id == user.id)


def run_scope_query(db: Session, user: User):
    """执行记录：企业用户仅本人资源（按用例归属 owner_id）。"""
    q = db.query(TestRun)
    if can_view_all_cases(user):
        return q
    return q.filter(TestRun.owner_id == user.id)
