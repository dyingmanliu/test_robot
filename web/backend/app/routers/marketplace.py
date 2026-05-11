"""数字机器人商城：目录浏览（需登录）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user
from app.models import User
from app.schemas import BillingModePriceOut, RobotCatalogItemOut, RobotCatalogResponse
from app.services.marketplace_catalog import list_robots

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


@router.get("/robots", response_model=RobotCatalogResponse)
def robots_catalog(_: User = Depends(get_current_user)) -> RobotCatalogResponse:
    items: list[RobotCatalogItemOut] = []
    for r in list_robots():
        bm = {k: BillingModePriceOut(**v) for k, v in r["billing_modes"].items()}
        items.append(
            RobotCatalogItemOut(
                id=r["id"],
                name=r["name"],
                category=r["category"],
                profile=r["profile"],
                capabilities=list(r["capabilities"]),
                billing_modes=bm,
            )
        )
    return RobotCatalogResponse(robots=items)
