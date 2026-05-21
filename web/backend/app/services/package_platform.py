"""根据安装包文件名或包名推断设备平台。"""

from __future__ import annotations

from app.services.device_platform import DevicePlatform, normalize_device_platform

_HARMONY_SUFFIXES = (".hap", ".app")
_ANDROID_SUFFIXES = (".apk", ".aab")


def infer_device_platform_from_package(
    *,
    bundle_id: str | None = None,
    filename: str | None = None,
    explicit: str | None = None,
) -> DevicePlatform:
    """优先显式平台，否则按包名/文件名后缀推断；无法识别时默认鸿蒙。"""
    if explicit and str(explicit).strip():
        return normalize_device_platform(explicit)
    for raw in (filename or "", bundle_id or ""):
        low = raw.strip().lower()
        if not low:
            continue
        for suf in _HARMONY_SUFFIXES:
            if low.endswith(suf):
                return "harmonyos"
        for suf in _ANDROID_SUFFIXES:
            if low.endswith(suf):
                return "android"
    return "harmonyos"


def platform_label_cn(platform: DevicePlatform) -> str:
    return "鸿蒙 / HDC" if platform == "harmonyos" else "Android / ADB"


_HARMONY_PREFIXES = ("鸿蒙", "harmony", "harmonyos", "hdc", "ohos", "鸿蒙os")
_ANDROID_PREFIXES = ("android", "安卓", "adb", "androidos")


def parse_platform_app_text(text: str) -> tuple[DevicePlatform, str]:
    """
    解析「平台 + 应用名」自然语言输入。
    示例：鸿蒙京东app → (harmonyos, 京东)；Android京东 → (android, 京东)
    """
    raw = (text or "").strip()
    if not raw:
        raise ValueError("请填写平台与应用名，例如：鸿蒙京东app、Android京东app")

    lower = raw.lower()
    platform: DevicePlatform | None = None
    rest = raw

    for p in _HARMONY_PREFIXES:
        if lower.startswith(p.lower()):
            platform = "harmonyos"
            rest = raw[len(p) :].strip()
            break
    if platform is None:
        for p in _ANDROID_PREFIXES:
            if lower.startswith(p.lower()):
                platform = "android"
                rest = raw[len(p) :].strip()
                break

    if platform is None:
        raise ValueError("请在开头标明平台：鸿蒙 / Android（安卓），例如「鸿蒙京东app」")

    app_name = rest.strip()
    if app_name.lower().endswith("app"):
        app_name = app_name[:-3].strip()
    if not app_name:
        raise ValueError("请填写应用名称，例如：鸿蒙京东app")

    return platform, app_name
