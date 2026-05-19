"""通过 HDC 查询设备已安装应用（bm dump -a）。"""

from __future__ import annotations

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


def list_installed_bundle_ids() -> list[str]:
    """执行 hdc shell bm dump -a，解析 bundleName 列表。"""
    hdc = _resolve_hdc_executable()
    device_id = (os.getenv("HDC_DEVICE_ID") or "").strip()
    cmd = [hdc]
    if device_id:
        cmd.extend(["-t", device_id])
    cmd.extend(["shell", "bm dump -a"])

    env = {**os.environ}
    if os.getenv("HDC_HOME"):
        env["HDC_HOME"] = os.environ["HDC_HOME"]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
            cwd=str(_REPO_ROOT),
        )
    except FileNotFoundError as e:
        raise RuntimeError(
            "未找到 hdc 命令，请配置 HDC_HOME 或将 hdc 加入 PATH"
        ) from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError("hdc bm dump -a 超时") from e

    out = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0 and not out.strip():
        raise RuntimeError(f"hdc bm dump -a 失败 (exit {result.returncode})")

    bundles: list[str] = []
    seen: set[str] = set()
    for line in out.splitlines():
        trimmed = line.strip()
        if not trimmed or trimmed.startswith("ID:") or trimmed.startswith("["):
            continue
        if re.match(r"^[a-zA-Z][a-zA-Z0-9._-]*$", trimmed) and "." in trimmed:
            if trimmed not in seen:
                seen.add(trimmed)
                bundles.append(trimmed)
    return sorted(bundles)
