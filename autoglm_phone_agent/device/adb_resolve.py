"""Locate the adb binary when it is not on the shell PATH (e.g. IDE-integrated terminals)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def resolve_adb_executable() -> str:
    """
    Return a usable ``adb`` path: ``shutil.which`` first, then common install locations.
    """
    found = shutil.which("adb")
    if found:
        return found

    home = Path.home()
    candidates = [
        home / "android" / "platform-tools" / "adb",
        Path("/opt/homebrew/bin/adb"),
        Path("/usr/local/bin/adb"),
        home / "Library/Android/sdk/platform-tools/adb",
    ]
    for p in candidates:
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)

    raise FileNotFoundError(
        "未找到 adb。请安装 Android platform-tools，例如：\n"
        "  - 将 platform-tools 解压到 ~/android/platform-tools/\n"
        "  - 或安装 Homebrew 后执行: brew install --cask android-platform-tools\n"
        "然后将 adb 所在目录加入 PATH，或使用上述默认路径。"
    )
