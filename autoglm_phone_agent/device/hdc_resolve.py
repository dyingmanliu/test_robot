# SPDX-License-Identifier: Apache-2.0
"""解析 HDC 可执行文件路径（参考 Open-AutoGLM / midscene_agent）。"""

from __future__ import annotations

import os
import shutil


def resolve_hdc_executable(hdc_home: str | None = None) -> str:
    raw = (hdc_home or os.getenv("HDC_HOME") or "").strip()
    if raw.endswith("/hdc") or raw.endswith("\\hdc"):
        return raw
    if raw and not _is_placeholder(raw):
        return f"{raw.rstrip('/')}/hdc"
    found = shutil.which("hdc")
    if found:
        return found
    return "hdc"


def _is_placeholder(value: str) -> bool:
    v = value.lower()
    return "/path/to" in v or "your-" in v or v in ("hdc", "bin")
