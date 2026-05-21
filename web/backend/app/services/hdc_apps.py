"""通过 HDC 查询设备已安装应用（bm dump -a / bm dump -a -l）。"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]


def _resolve_hdc_executable() -> str:
    raw = (os.getenv("HDC_HOME") or "").strip()
    if raw:
        if raw.endswith("/hdc") or raw.endswith("\\hdc"):
            return raw
        return f"{raw.rstrip('/')}/hdc"
    found = shutil.which("hdc")
    return found or "hdc"


def _hdc_cmd(shell_args: list[str], *, device_id: str | None = None) -> list[str]:
    hdc = _resolve_hdc_executable()
    cmd = [hdc]
    dev = (device_id or os.getenv("HDC_DEVICE_ID") or "").strip()
    if dev:
        cmd.extend(["-t", dev])
    cmd.extend(["shell", *shell_args])
    return cmd


def _run_hdc_shell(shell_args: list[str], *, device_id: str | None = None, timeout: int = 90) -> str:
    env = {**os.environ}
    if os.getenv("HDC_HOME"):
        env["HDC_HOME"] = os.environ["HDC_HOME"]
    try:
        result = subprocess.run(
            _hdc_cmd(shell_args, device_id=device_id),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=str(_REPO_ROOT),
        )
    except FileNotFoundError as e:
        raise RuntimeError("未找到 hdc 命令，请配置 HDC_HOME 或将 hdc 加入 PATH") from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"hdc shell {' '.join(shell_args)} 超时") from e

    out = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0 and not out.strip():
        raise RuntimeError(f"hdc shell 失败 (exit {result.returncode})")
    return out


def _fallback_label(bundle_id: str) -> str:
    return bundle_id.rsplit(".", 1)[-1] if "." in bundle_id else bundle_id


def _parse_bundle_lines(text: str) -> list[str]:
    bundles: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        trimmed = line.strip()
        if not trimmed or trimmed.startswith("ID:") or trimmed.startswith("["):
            continue
        if re.match(r"^[a-zA-Z][a-zA-Z0-9._-]*$", trimmed) and "." in trimmed:
            if trimmed not in seen:
                seen.add(trimmed)
                bundles.append(trimmed)
    return sorted(bundles)


def _parse_labeled_json(text: str) -> list[tuple[str, str]]:
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end <= start:
        return []
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    apps: list[tuple[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        bundle_id = str(item.get("bundleName") or item.get("bundle_name") or "").strip()
        if not bundle_id:
            continue
        label = str(item.get("label") or "").strip()
        apps.append((bundle_id, label or _fallback_label(bundle_id)))
    apps.sort(key=lambda x: (x[1], x[0]))
    return apps


def list_installed_harmony_apps(*, device_id: str | None = None) -> list[tuple[str, str]]:
    """返回 (bundle_id, 显示名)；优先 bm dump -a -l 获取中文 label。"""
    labeled = _parse_labeled_json(_run_hdc_shell(["bm", "dump", "-a", "-l"], device_id=device_id))
    if labeled:
        return labeled

    plain = _run_hdc_shell(["bm", "dump", "-a"], device_id=device_id)
    return [(b, _fallback_label(b)) for b in _parse_bundle_lines(plain)]


def list_installed_bundle_ids(*, device_id: str | None = None) -> list[str]:
    """执行 hdc shell bm dump -a，解析 bundleName 列表。"""
    return [b for b, _ in list_installed_harmony_apps(device_id=device_id)]
