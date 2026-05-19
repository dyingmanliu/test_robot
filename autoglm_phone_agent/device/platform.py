# SPDX-License-Identifier: Apache-2.0
"""设备平台类型（对齐 Open-AutoGLM --device-type adb|hdc）。"""

from __future__ import annotations

from enum import Enum


class DevicePlatform(str, Enum):
    ANDROID = "android"
    HARMONYOS = "harmonyos"

    @classmethod
    def parse(cls, raw: str | None) -> DevicePlatform:
        p = (raw or "android").strip().lower()
        if p in ("harmonyos", "harmony", "hmos", "ohos", "hdc"):
            return cls.HARMONYOS
        return cls.ANDROID

    @property
    def open_autoglm_device_type(self) -> str:
        """Open-AutoGLM CLI 参数值。"""
        return "hdc" if self == DevicePlatform.HARMONYOS else "adb"
