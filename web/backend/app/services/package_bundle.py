"""从安装包文件或安装前后设备列表差异解析 bundle_id。"""

from __future__ import annotations

import json
import re
import subprocess
import zipfile
from pathlib import Path


def infer_bundle_id_from_package(file_path: Path) -> str:
    """从 .hap / .app / .apk / .aab 推断 bundle_id（包名）。"""
    if not file_path.is_file():
        return ""
    ext = file_path.suffix.lower()
    if ext in (".hap", ".app"):
        return _bundle_from_hap_archive(file_path)
    if ext in (".apk", ".aab"):
        return _bundle_from_apk(file_path)
    return ""


_INSTALLER_HINTS = (
    "qqdownloader",
    "appmarket",
    "appstore",
    "packageinstaller",
    "vivoinstall",
    "miui.packageinstaller",
    "huawei.appmarket",
    "honor.appmarket",
    "samsungapps",
    "wandoujia",
    "yyb",
)


def _is_likely_installer(bundle_id: str) -> bool:
    low = bundle_id.lower()
    return any(h in low for h in _INSTALLER_HINTS)


def resolve_bundle_after_install(
    *,
    platform: str,
    file_path: Path,
    before: set[str],
    after_entries: list[tuple[str, str]],
) -> tuple[str, str]:
    """
    安装后确定 bundle_id 与显示名。
    优先：安装包内解析且已在设备上；其次：安装前后差集（排除应用商店/安装器）。
    """
    after_ids = {b for b, _ in after_entries}
    new_ids = after_ids - before
    guessed = infer_bundle_id_from_package(file_path)

    bundle_id = ""
    if guessed and guessed in after_ids:
        bundle_id = guessed
    elif len(new_ids) == 1:
        bundle_id = next(iter(new_ids))
    elif len(new_ids) > 1:
        non_installer = [b for b in new_ids if not _is_likely_installer(b)]
        if len(non_installer) == 1:
            bundle_id = non_installer[0]
        elif guessed:
            bundle_id = guessed
        elif non_installer:
            bundle_id = sorted(non_installer)[0]
        else:
            bundle_id = sorted(new_ids)[0]
    elif guessed:
        bundle_id = guessed

    if not bundle_id or "." not in bundle_id:
        raise ValueError(
            "安装已完成，但无法自动识别应用包名。请确认设备在线且安装包有效后重试。"
        )

    labels = {b: label for b, label in after_entries}
    label = (labels.get(bundle_id) or "").strip()
    if not label:
        label = bundle_id.rsplit(".", 1)[-1] if "." in bundle_id else bundle_id
    return bundle_id, label


def _bundle_from_hap_archive(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                low = name.lower()
                if not (low.endswith("pack.info") or low.endswith("module.json")):
                    continue
                try:
                    raw = zf.read(name)
                    data = json.loads(raw.decode("utf-8", errors="ignore"))
                except (json.JSONDecodeError, KeyError, UnicodeDecodeError):
                    continue
                found = _extract_bundle_from_json(data)
                if found:
                    return found
    except (zipfile.BadZipFile, OSError):
        pass
    return ""


def _extract_bundle_from_json(data: object) -> str:
    if not isinstance(data, dict):
        return ""
    app = data.get("app")
    if isinstance(app, dict):
        bn = str(app.get("bundleName") or app.get("bundle_name") or "").strip()
        if bn and "." in bn:
            return bn
    summary = data.get("summary")
    if isinstance(summary, dict):
        app2 = summary.get("app")
        if isinstance(app2, dict):
            bn = str(app2.get("bundleName") or app2.get("bundle_name") or "").strip()
            if bn and "." in bn:
                return bn
    module = data.get("module")
    if isinstance(module, dict):
        bn = str(module.get("bundleName") or "").strip()
        if bn and "." in bn:
            return bn
    return ""


def _bundle_from_apk(path: Path) -> str:
    for cmd in (
        ["aapt", "dump", "badging", str(path)],
        ["aapt2", "dump", "badging", str(path)],
    ):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
        if result.returncode != 0:
            continue
        m = re.search(r"package:\s*name='([^']+)'", result.stdout or "")
        if m:
            return m.group(1).strip()
    return ""
