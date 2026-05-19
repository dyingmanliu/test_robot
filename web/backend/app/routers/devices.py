"""本机已连接设备枚举（ADB / HDC）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.deps import get_current_user
from app.models import User
from app.schemas import ConnectedDeviceOut, ConnectedDevicesOut
from app.services.device_discovery import list_connected_devices
from app.services.device_platform import normalize_device_platform

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("/connected", response_model=ConnectedDevicesOut)
def get_connected_devices(
    platform: str = Query("android", description="android 或 harmonyos"),
    user: User = Depends(get_current_user),
) -> ConnectedDevicesOut:
    _ = user
    plat = normalize_device_platform(platform)
    try:
        rows = list_connected_devices(plat)
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        ) from e
    return ConnectedDevicesOut(
        platform=plat,
        devices=[
            ConnectedDeviceOut(
                device_id=d.device_id,
                label=d.label,
                state=d.state,
            )
            for d in rows
        ],
    )
