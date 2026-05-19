"""枚举本机已连接的 Android（ADB）与鸿蒙（HDC）设备。"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ConnectedDevice:
    device_id: str
    label: str
    state: str
    platform: str


def _resolve_adb() -> str:
    found = shutil.which("adb")
    if found:
        return found
    home = Path.home()
    for p in (
        home / "android" / "platform-tools" / "adb",
        Path("/opt/homebrew/bin/adb"),
        Path("/usr/local/bin/adb"),
        home / "Library/Android/sdk/platform-tools/adb",
    ):
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
    raise FileNotFoundError(
        "未找到 adb。请安装 Android platform-tools 并加入 PATH，或配置 ~/android/platform-tools/"
    )


def _resolve_hdc() -> str:
    raw = (os.getenv("HDC_HOME") or "").strip()
    if raw.endswith("/hdc") or raw.endswith("\\hdc"):
        return raw
    if raw and "/path/to" not in raw.lower():
        return f"{raw.rstrip('/')}/hdc"
    return shutil.which("hdc") or "hdc"


def _parse_adb_model(line: str) -> str | None:
    m = re.search(r"\bmodel:(\S+)", line)
    return m.group(1) if m else None


def list_android_devices(*, timeout: int = 15) -> list[ConnectedDevice]:
    try:
        result = subprocess.run(
            [_resolve_adb(), "devices", "-l"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as e:
        raise RuntimeError(str(e)) from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError("adb devices 超时") from e

    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(err or f"adb devices 失败 (code {result.returncode})")

    devices: list[ConnectedDevice] = []
    for line in (result.stdout or "").splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        model = _parse_adb_model(line)
        label = f"{model} ({serial})" if model else serial
        devices.append(
            ConnectedDevice(
                device_id=serial,
                label=label,
                state=state,
                platform="android",
            )
        )
    return devices


def list_harmonyos_devices(*, timeout: int = 15) -> list[ConnectedDevice]:
    hdc = _resolve_hdc()
    env = {**os.environ}
    if os.getenv("HDC_HOME"):
        env["HDC_HOME"] = os.getenv("HDC_HOME", "")
    try:
        result = subprocess.run(
            [hdc, "list", "targets"],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except FileNotFoundError as e:
        raise RuntimeError(
            "未找到 hdc。请安装 DevEco Studio 并配置 HDC_HOME 或 PATH。"
        ) from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError("hdc list targets 超时") from e

    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(err or f"hdc list targets 失败 (code {result.returncode})")

    devices: list[ConnectedDevice] = []
    for line in (result.stdout or "").splitlines():
        device_id = line.strip()
        if not device_id or device_id.startswith("[Empty]"):
            continue
        devices.append(
            ConnectedDevice(
                device_id=device_id,
                label=device_id,
                state="device",
                platform="harmonyos",
            )
        )
    return devices


def list_connected_devices(platform: str) -> list[ConnectedDevice]:
    p = (platform or "android").strip().lower()
    if p in ("harmonyos", "harmony", "hmos", "ohos"):
        return list_harmonyos_devices()
    return list_android_devices()
