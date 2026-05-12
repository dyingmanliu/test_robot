"""内置 RBAC：预定义角色与数据范围辅助函数。

网关可校验 JWT `role` 声明；服务内以数据库 `users.role` 为准并做一次一致性提示。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import User

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


def case_scope_filter(db: Session, query, user: User):
    """测试用例列表/查询：企业用户默认仅本人；公司开启内部共享后含同事用例。"""
    from app.services.company_scope import case_scope_query

    return case_scope_query(db, query, user)


def run_scope_query(db: Session, user: User):
    """执行记录：与用例 owner 范围一致（公司内部共享时含同事）。"""
    from app.services.company_scope import run_scope_query as company_run_scope_query

    return company_run_scope_query(db, user)
