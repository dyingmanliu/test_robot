"""租用申请：数量与账单、待审批（不跳转支付）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import RobotRentalOrder, User
from app.schemas import RentalOrderCreate, RentalOrderCreatedOut, RentalOrderOut
from app.services.marketplace_catalog import get_robot_by_id

router = APIRouter(prefix="/rentals", tags=["rentals"])


@router.post("/orders", response_model=RentalOrderCreatedOut)
def create_rental_order(
    body: RentalOrderCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RentalOrderCreatedOut:
    robot = get_robot_by_id(body.robot_id.strip())
    if robot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到该数字机器人")
    cfg = robot["billing_modes"].get(body.billing_mode)
    if cfg is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该机器人不支持此计费模式")

    unit = int(cfg["price_cents"])
    total = unit * body.quantity
    row = RobotRentalOrder(
        user_id=user.id,
        company_id=user.company_id,
        robot_id=robot["id"],
        robot_name=robot["name"],
        billing_mode=body.billing_mode,
        quantity=body.quantity,
        unit_price_cents=unit,
        total_cents=total,
        currency="CNY",
        status="pending_approval",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return RentalOrderCreatedOut(
        id=row.id,
        status=row.status,
        quantity=row.quantity,
        unit_price_cents=row.unit_price_cents,
        total_cents=row.total_cents,
        currency=row.currency,
        robot_id=row.robot_id,
        robot_name=row.robot_name,
        billing_mode=row.billing_mode,
    )


@router.get("/orders/mine", response_model=list[RentalOrderOut])
def list_my_rental_orders(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RobotRentalOrder]:
    q = db.query(RobotRentalOrder)
    if user.company_id is not None:
        q = q.filter(RobotRentalOrder.company_id == user.company_id)
    else:
        q = q.filter(RobotRentalOrder.user_id == user.id)
    return q.order_by(RobotRentalOrder.id.desc()).limit(100).all()
