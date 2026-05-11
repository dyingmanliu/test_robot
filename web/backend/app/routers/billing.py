"""计费模块：预订单创建与查询（支付网关对接前的占位流转）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import BillingPreorder, User
from app.schemas import PreorderCreate, PreorderCreatedOut, PreorderDetailOut
from app.services.marketplace_catalog import get_robot_by_id

router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("/preorders", response_model=PreorderCreatedOut)
def create_preorder(
    body: PreorderCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PreorderCreatedOut:
    robot = get_robot_by_id(body.robot_id.strip())
    if robot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到该数字机器人")
    cfg = robot["billing_modes"].get(body.billing_mode)
    if cfg is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该机器人不支持此计费模式")

    row = BillingPreorder(
        user_id=user.id,
        robot_id=robot["id"],
        robot_name=robot["name"],
        billing_mode=body.billing_mode,
        amount_cents=int(cfg["price_cents"]),
        currency="CNY",
        status="pending_payment",
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    payment_path = f"/payment?preorderId={row.id}"
    return PreorderCreatedOut(
        preorder_id=row.id,
        status=row.status,
        payment_path=payment_path,
        amount_cents=row.amount_cents,
        currency=row.currency,
    )


@router.get("/preorders/{preorder_id}", response_model=PreorderDetailOut)
def get_preorder(
    preorder_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PreorderDetailOut:
    row = db.query(BillingPreorder).filter(BillingPreorder.id == preorder_id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预订单不存在")
    if row.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该预订单")
    return PreorderDetailOut.model_validate(row)
