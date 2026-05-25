"""设备 ID 解析：优先传入值，否则回退到环境变量。"""

from __future__ import annotations

import os


def resolve_execution_device_id(
    *,
    run_device_id: str | None,
    device_platform: str,
) -> str | None:
    raw = (run_device_id or "").strip()
    if raw:
        return raw
    env_key = "HDC_DEVICE_ID" if device_platform == "harmonyos" else "ADB_DEVICE_ID"
    fallback = (os.getenv(env_key) or "").strip()
    return fallback or None
