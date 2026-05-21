"""将项目安装包安装到真机（Android ADB / 鸿蒙 HDC）。"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from app.services.device_discovery import _resolve_adb, _resolve_hdc
from app.services.device_platform import normalize_device_platform

# (bundle_id, display_label)
InstalledAppEntry = tuple[str, str]


def list_installed_packages(platform: str, *, device_id: str | None = None) -> list[str]:
    """兼容旧接口：仅返回 bundle_id 列表。"""
    return [b for b, _ in list_installed_apps(platform, device_id=device_id)]


def list_installed_apps(platform: str, *, device_id: str | None = None) -> list[InstalledAppEntry]:
    """返回 (bundle_id, 显示名)；鸿蒙优先中文 label，Android 尽力解析。"""
    plat = normalize_device_platform(platform)
    if plat == "android":
        return _list_android_apps(device_id)
    return _list_harmony_apps(device_id)


def install_package_file(
    file_path: Path,
    platform: str,
    *,
    device_id: str | None = None,
) -> str:
    plat = normalize_device_platform(platform)
    if not file_path.is_file():
        raise FileNotFoundError(f"安装包不存在：{file_path}")
    ext = file_path.suffix.lower()
    if plat == "android":
        if ext not in (".apk", ".aab"):
            raise ValueError("Android 仅支持 .apk / .aab 安装包")
        return _adb_install(file_path, device_id)
    if ext not in (".hap", ".app", ".apk"):
        raise ValueError("鸿蒙支持 .hap / .app（部分环境可用 .apk）")
    return _hdc_install(file_path, device_id)


def _adb_args(device_id: str | None) -> list[str]:
    cmd = [_resolve_adb()]
    if device_id and device_id.strip():
        cmd.extend(["-s", device_id.strip()])
    return cmd


def _hdc_args(device_id: str | None) -> list[str]:
    cmd = [_resolve_hdc()]
    if device_id and device_id.strip():
        cmd.extend(["-t", device_id.strip()])
    return cmd


def _adb_install(path: Path, device_id: str | None) -> str:
    cmd = _adb_args(device_id) + ["install", "-r", str(path)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    out = ((result.stdout or "") + (result.stderr or "")).strip()
    if result.returncode != 0 or "Failure" in out:
        raise RuntimeError(out or f"adb install 失败 (code {result.returncode})")
    return out or "Success"


def _hdc_install(path: Path, device_id: str | None) -> str:
    cmd = _hdc_args(device_id) + ["install", str(path)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    out = ((result.stdout or "") + (result.stderr or "")).strip()
    if result.returncode != 0:
        raise RuntimeError(out or f"hdc install 失败 (code {result.returncode})")
    return out or "install ok"


def _fallback_label(bundle_id: str) -> str:
    return bundle_id.rsplit(".", 1)[-1] if "." in bundle_id else bundle_id


def _parse_android_label(dumpsys_out: str) -> str:
    for key in (
        "application-label-zh-CN",
        "application-label-zh",
        "application-label-zh-Hans",
        "application-label",
    ):
        for line in dumpsys_out.splitlines():
            if key not in line:
                continue
            m = re.search(rf"{re.escape(key)}='([^']*)'", line)
            if not m:
                m = re.search(rf'{re.escape(key)}="([^"]*)"', line)
            if m and m.group(1).strip():
                return m.group(1).strip()
    return ""


def _list_android_user_package_ids(device_id: str | None) -> list[str]:
    cmd = _adb_args(device_id) + ["shell", "pm", "list", "packages", "-3"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "pm list packages 失败").strip())
    out: list[str] = []
    for line in (result.stdout or "").splitlines():
        line = line.strip()
        if line.startswith("package:"):
            out.append(line.split(":", 1)[1].strip())
    return sorted(set(out))


def _list_android_apps(device_id: str | None) -> list[InstalledAppEntry]:
    pkgs = _list_android_user_package_ids(device_id)
    apps: list[InstalledAppEntry] = []
    for pkg in pkgs:
        cmd = _adb_args(device_id) + ["shell", "dumpsys", "package", pkg]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        label = ""
        if result.returncode == 0:
            label = _parse_android_label(result.stdout or "")
        apps.append((pkg, label or _fallback_label(pkg)))
    apps.sort(key=lambda x: (x[1], x[0]))
    return apps


def _list_harmony_apps(device_id: str | None) -> list[InstalledAppEntry]:
    from app.services.hdc_apps import list_installed_harmony_apps

    return list_installed_harmony_apps(device_id=device_id)
