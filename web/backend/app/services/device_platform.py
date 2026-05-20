"""设备平台解析：与 test_agent_backend（执行引擎）解耦。"""

from __future__ import annotations

from typing import Literal

DevicePlatform = Literal["android", "harmonyos"]


def normalize_device_platform(value: str | None) -> DevicePlatform:
    p = (value or "").strip().lower()
    if p in ("harmonyos", "harmony", "hmos", "ohos"):
        return "harmonyos"
    return "android"


def default_platform_for_backend(backend: str | None) -> DevicePlatform:
    """历史兼容：未配置 device_platform 时按引擎推断默认平台。"""
    b = (backend or "autoglm").strip().lower()
    return "harmonyos" if b == "midscene" else "android"


def resolve_instance_platform(
    *,
    device_platform: str | None,
    test_agent_backend: str | None,
) -> DevicePlatform:
    raw = (device_platform or "").strip()
    if raw:
        return normalize_device_platform(raw)
    return default_platform_for_backend(test_agent_backend)


def resolve_execution_platform(
    *,
    run_device_platform: str | None,
    instance_device_platform: str | None,
    test_agent_backend: str | None,
) -> DevicePlatform:
    """单次执行平台：优先 run 覆盖，否则实例默认。"""
    raw = (run_device_platform or "").strip()
    if raw:
        return normalize_device_platform(raw)
    return resolve_instance_platform(
        device_platform=instance_device_platform,
        test_agent_backend=test_agent_backend,
    )


def uses_midscene_runner(*, test_agent_backend: str | None, device_platform: DevicePlatform) -> bool:
    """是否通过 midscene_tech 子进程执行（仅 Midscene 引擎）。"""
    _ = device_platform
    return (test_agent_backend or "autoglm").strip().lower() == "midscene"


def uses_autoglm_runner(*, test_agent_backend: str | None, device_platform: DevicePlatform) -> bool:
    """是否通过 autoglm_phone_tech 同进程执行（Android / 鸿蒙）。"""
    _ = device_platform
    return (test_agent_backend or "autoglm").strip().lower() == "autoglm"


def platform_label(platform: DevicePlatform) -> str:
    return "鸿蒙 / HDC" if platform == "harmonyos" else "Android / ADB"


def resolve_execution_device_id(
    *,
    run_device_id: str | None,
    device_platform: DevicePlatform,
) -> str | None:
    """单次执行设备 ID：优先 run 指定，否则 .env 默认。"""
    raw = (run_device_id or "").strip()
    if raw:
        return raw
    import os

    env_key = "HDC_DEVICE_ID" if device_platform == "harmonyos" else "ADB_DEVICE_ID"
    fallback = (os.getenv(env_key) or "").strip()
    return fallback or None
