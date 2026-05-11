"""设备池列表（占位）：供功能测试下发向导选择。"""

from __future__ import annotations

from fastapi import APIRouter

from app.services.device_pools import list_device_pools

router = APIRouter(prefix="/device-pools", tags=["device-pools"])


@router.get("")
def get_device_pools() -> dict:
    return {"pools": list_device_pools()}
