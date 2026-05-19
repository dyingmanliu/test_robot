# SPDX-License-Identifier: Apache-2.0
"""设备工厂：按平台返回 ADB / HDC 实现（对齐 Open-AutoGLM device_factory）。"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Union

from autoglm_phone_agent.device.adb_bridge import AdbBridge
from autoglm_phone_agent.device.hdc_bridge import HdcBridge
from autoglm_phone_agent.device.platform import DevicePlatform

if TYPE_CHECKING:
    DeviceBridge = Union[AdbBridge, HdcBridge]
else:
    DeviceBridge = Union[AdbBridge, HdcBridge]

def create_device(
    platform: DevicePlatform | str | None = None,
    *,
    device_id: str | None = None,
) -> DeviceBridge:
    plat = (
        platform
        if isinstance(platform, DevicePlatform)
        else DevicePlatform.parse(str(platform) if platform else None)
    )
    if device_id is None:
        device_id = (
            os.getenv("HDC_DEVICE_ID")
            if plat == DevicePlatform.HARMONYOS
            else os.getenv("ADB_DEVICE_ID")
        ) or None

    if plat == DevicePlatform.HARMONYOS:
        return HdcBridge(device_id=device_id)
    return AdbBridge(device_id=device_id)


def get_device_factory(
    platform: DevicePlatform | str | None = None,
    *,
    device_id: str | None = None,
) -> DeviceBridge:
    return create_device(platform, device_id=device_id)
