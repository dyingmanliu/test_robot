"""平台管理员：用户与角色管理（RBAC）。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_roles
from app.models import Company, RobotInstance, RobotRentalOrder, User
from app.rbac import ROLE_PLATFORM_ADMIN, ROLE_LABELS, ROLES
from app.schemas import (
    AdminRolePatch,
    AdminUserOut,
    CompanyAdminOut,
    CompanySharePatch,
    RentalApproveBody,
    RentalOrderOut,
    RentalRejectBody,
    RobotInstanceOut,
    RobotInstanceStatusPatch,
)
from app.services.robot_instance_out import robot_instance_to_out

router = APIRouter(prefix="/admin", tags=["admin"])


def _next_instance_codes(db: Session, count: int) -> list[str]:
    n = db.query(func.count(RobotInstance.id)).scalar() or 0
    return [f"DR-{n + i + 1:06d}" for i in range(count)]


@router.get("/rental-orders", response_model=list[RentalOrderOut])
def list_rental_orders(
    status: Optional[str] = Query(None, description="按状态筛选，如 pending_approval"),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(ROLE_PLATFORM_ADMIN)),
) -> list[RobotRentalOrder]:
    q = db.query(RobotRentalOrder).order_by(RobotRentalOrder.id.desc())
    if status:
        q = q.filter(RobotRentalOrder.status == status)
    return q.limit(200).all()


@router.post("/rental-orders/{order_id}/approve", response_model=RentalOrderOut)
def approve_rental_order(
    order_id: int,
    body: RentalApproveBody = Body(default=RentalApproveBody()),
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(ROLE_PLATFORM_ADMIN)),
) -> RobotRentalOrder:
    row = db.query(RobotRentalOrder).filter(RobotRentalOrder.id == order_id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="租用单不存在")
    if row.status != "pending_approval":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该租用单不在待审批状态")

    codes = _next_instance_codes(db, row.quantity)
    for code in codes:
        db.add(
            RobotInstance(
                rental_order_id=row.id,
                user_id=row.user_id,
                company_id=row.company_id,
                catalog_robot_id=row.robot_id,
                instance_code=code,
                display_name=row.robot_name,
                display_bio="",
                status="active",
                test_agent_backend=body.test_agent_backend,
                device_platform=body.device_platform,
            )
        )
    row.status = "approved"
    row.reviewed_at = datetime.utcnow()
    row.reviewer_user_id = admin.id
    row.reject_reason = None
    db.commit()
    db.refresh(row)
    return row


@router.post("/rental-orders/{order_id}/reject", response_model=RentalOrderOut)
def reject_rental_order(
    order_id: int,
    body: RentalRejectBody,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(ROLE_PLATFORM_ADMIN)),
) -> RobotRentalOrder:
    row = db.query(RobotRentalOrder).filter(RobotRentalOrder.id == order_id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="租用单不存在")
    if row.status != "pending_approval":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该租用单不在待审批状态")
    row.status = "rejected"
    row.reviewed_at = datetime.utcnow()
    row.reviewer_user_id = admin.id
    row.reject_reason = (body.reason or "").strip() or None
    db.commit()
    db.refresh(row)
    return row


@router.get("/companies", response_model=list[CompanyAdminOut])
def list_companies(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(ROLE_PLATFORM_ADMIN)),
) -> list[CompanyAdminOut]:
    rows = db.query(Company).order_by(Company.id.desc()).all()
    out: list[CompanyAdminOut] = []
    for c in rows:
        n_users = db.query(func.count(User.id)).filter(User.company_id == c.id).scalar() or 0
        out.append(
            CompanyAdminOut(
                id=c.id,
                name=c.name,
                share_projects_cases_internally=bool(c.share_projects_cases_internally),
                user_count=int(n_users),
            )
        )
    return out


@router.patch("/companies/{company_id}/share-internal", response_model=CompanyAdminOut)
def patch_company_share_internal(
    company_id: int,
    body: CompanySharePatch,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(ROLE_PLATFORM_ADMIN)),
) -> CompanyAdminOut:
    c = db.query(Company).filter(Company.id == company_id).first()
    if c is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="公司不存在")
    c.share_projects_cases_internally = bool(body.share_projects_cases_internally)
    db.commit()
    db.refresh(c)
    n_users = db.query(func.count(User.id)).filter(User.company_id == c.id).scalar() or 0
    return CompanyAdminOut(
        id=c.id,
        name=c.name,
        share_projects_cases_internally=bool(c.share_projects_cases_internally),
        user_count=int(n_users),
    )


@router.get("/robot-instances", response_model=list[RobotInstanceOut])
def list_robot_instances_admin(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(ROLE_PLATFORM_ADMIN)),
) -> list[RobotInstanceOut]:
    rows = db.query(RobotInstance).order_by(RobotInstance.id.desc()).limit(500).all()
    return [robot_instance_to_out(db, inst) for inst in rows]


@router.patch("/robot-instances/{instance_id}/status", response_model=RobotInstanceOut)
def set_robot_instance_status_admin(
    instance_id: int,
    body: RobotInstanceStatusPatch,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(ROLE_PLATFORM_ADMIN)),
) -> RobotInstanceOut:
    inst = db.query(RobotInstance).filter(RobotInstance.id == instance_id).first()
    if inst is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="机器人实例不存在")
    inst.status = body.status
    db.commit()
    db.refresh(inst)
    return robot_instance_to_out(db, inst)


@router.get("/users", response_model=list[AdminUserOut])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(ROLE_PLATFORM_ADMIN)),
) -> list[User]:
    return db.query(User).order_by(User.id.desc()).all()


@router.get("/rbac/roles", response_model=dict[str, str])
def list_role_definitions(
    _: User = Depends(require_roles(ROLE_PLATFORM_ADMIN)),
) -> dict[str, str]:
    """预定义角色说明，供管理端展示。"""
    return {r: ROLE_LABELS.get(r, r) for r in ROLES}


@router.patch("/users/{user_id}/role", response_model=AdminUserOut)
def set_user_role(
    user_id: int,
    body: AdminRolePatch,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(ROLE_PLATFORM_ADMIN)),
) -> User:
    if user_id == admin.id and body.role != ROLE_PLATFORM_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能自行取消平台管理员角色",
        )
    u = db.query(User).filter(User.id == user_id).first()
    if u is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    u.role = body.role
    db.commit()
    db.refresh(u)
    return u
