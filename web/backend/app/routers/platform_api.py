"""跨服务能力的占位路由：设备、计费、机器人目录等，均按 RBAC 隔离。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import require_roles
from app.models import User
from app.rbac import ROLE_ENTERPRISE, ROLE_PLATFORM_ADMIN, ROLE_TSE

router = APIRouter(prefix="/platform", tags=["platform"])


@router.get("/devices")
def platform_devices(
    _: User = Depends(require_roles(ROLE_PLATFORM_ADMIN)),
) -> dict:
    """设备管理（占位）：对接设备管理服务后返回实例与健康状态。"""
    return {
        "scope": "global",
        "items": [],
        "message": "仅平台管理员可访问；数据来自设备管理域。",
    }


@router.get("/billing-config")
def platform_billing_config(
    _: User = Depends(require_roles(ROLE_PLATFORM_ADMIN)),
) -> dict:
    """计费配置（占位）：套餐、计量规则等。"""
    return {
        "plans": [],
        "message": "仅平台管理员可配置计费策略。",
    }


@router.get("/robots/catalog")
def robot_catalog_full(
    _: User = Depends(require_roles(ROLE_PLATFORM_ADMIN, ROLE_TSE)),
) -> dict:
    """全量数字机器人能力目录（TSE / 管理员）。"""
    return {
        "robots": [
            {"id": "autoglm-phone", "name": "手机端 UI 自动化", "tenant_scope": False},
        ],
        "message": "内部测试工程师可使用全部能力；企业租户为租用子集。",
    }


@router.get("/enterprise/robot-rentals")
def enterprise_robot_rentals(
    user: User = Depends(require_roles(ROLE_ENTERPRISE)),
) -> dict:
    """外部企业租用中的机器人实例（占位）。"""
    return {
        "tenant_id": user.id,
        "rentals": [],
        "message": "仅外部企业用户可见自身租用范围。",
    }


@router.get("/enterprise/usage-report")
def enterprise_usage_report(
    user: User = Depends(require_roles(ROLE_ENTERPRISE)),
) -> dict:
    """外部企业消费与报告（占位）。"""
    return {
        "tenant_id": user.id,
        "consumption": [],
        "reports": [],
        "message": "仅展示本企业项目空间下的消费与报告。",
    }
