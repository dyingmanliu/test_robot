# SPDX-License-Identifier: Apache-2.0
# Patterns adapted from Open-AutoGLM phone_agent/adb/

from __future__ import annotations

import base64
import os
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from io import BytesIO

from PIL import Image

from autoglm_phone_tech.config.apps import APP_PACKAGES
from autoglm_phone_tech.config.timing import (
    DEFAULT_BACK_DELAY,
    DEFAULT_DOUBLE_TAP_DELAY,
    DEFAULT_HOME_DELAY,
    DEFAULT_LAUNCH_DELAY,
    DEFAULT_LONG_PRESS_DELAY,
    DEFAULT_SWIPE_DELAY,
    DEFAULT_TAP_DELAY,
    DOUBLE_TAP_INTERVAL,
)

from autoglm_phone_tech.device.adb_resolve import resolve_adb_executable


@dataclass
class Screenshot:
    base64_data: str
    width: int
    height: int
    is_sensitive: bool = False


_adb_cached: str | None = None


def _adb_bin() -> str:
    global _adb_cached
    if _adb_cached is None:
        _adb_cached = resolve_adb_executable()
    return _adb_cached


def _adb_prefix(device_id: str | None) -> list[str]:
    exe = _adb_bin()
    return [exe, "-s", device_id] if device_id else [exe]


class AdbBridge:
    """Thin ADB wrapper used by the action handler."""

    def __init__(self, device_id: str | None = None) -> None:
        self.device_id = device_id

    def _p(self) -> list[str]:
        return _adb_prefix(self.device_id)

    def get_current_app(self) -> str:
        result = subprocess.run(
            self._p() + ["shell", "dumpsys", "window"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        output = result.stdout or ""
        for line in output.split("\n"):
            if "mCurrentFocus" in line or "mFocusedApp" in line:
                for app_name, package in APP_PACKAGES.items():
                    if package in line:
                        return app_name
        return "System Home"

    def get_screenshot(self, timeout: int = 10) -> Screenshot:
        max_width = int(os.getenv("DEVICE_SCREEN_MAX_WIDTH", "720"))
        jpeg_quality = int(os.getenv("DEVICE_SCREEN_JPEG_QUALITY", "75"))
        temp_path = os.path.join(tempfile.gettempdir(), f"screenshot_{uuid.uuid4()}.png")
        try:
            result = subprocess.run(
                self._p() + ["shell", "screencap", "-p", "/sdcard/tmp_autoglm.png"],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            out = (result.stdout or "") + (result.stderr or "")
            if "Status: -1" in out or "Failed" in out:
                return _fallback(True)

            subprocess.run(
                self._p() + ["pull", "/sdcard/tmp_autoglm.png", temp_path],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if not os.path.exists(temp_path):
                return _fallback(False)

            img = Image.open(temp_path)
            width, height = img.size
            if width > max_width:
                ratio = max_width / width
                img = img.resize((max_width, int(height * ratio)), Image.LANCZOS)
                width, height = img.size
            buffered = BytesIO()
            img.save(buffered, format="JPEG", quality=jpeg_quality)
            b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
            os.remove(temp_path)
            return Screenshot(base64_data=b64, width=width, height=height, is_sensitive=False)
        except Exception as e:
            print(f"Screenshot error: {e}")
            return _fallback(False)

    def launch_app(self, app_name: str) -> bool:
        if app_name not in APP_PACKAGES:
            return False
        package = APP_PACKAGES[app_name]
        subprocess.run(
            self._p()
            + ["shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"],
            capture_output=True,
        )
        time.sleep(DEFAULT_LAUNCH_DELAY)
        return True

    def tap(self, x: int, y: int) -> None:
        subprocess.run(self._p() + ["shell", "input", "tap", str(x), str(y)], capture_output=True)
        time.sleep(DEFAULT_TAP_DELAY)

    def double_tap(self, x: int, y: int) -> None:
        subprocess.run(self._p() + ["shell", "input", "tap", str(x), str(y)], capture_output=True)
        time.sleep(DOUBLE_TAP_INTERVAL)
        subprocess.run(self._p() + ["shell", "input", "tap", str(x), str(y)], capture_output=True)
        time.sleep(DEFAULT_DOUBLE_TAP_DELAY)

    def long_press(self, x: int, y: int, duration_ms: int = 3000) -> None:
        subprocess.run(
            self._p()
            + ["shell", "input", "swipe", str(x), str(y), str(x), str(y), str(duration_ms)],
            capture_output=True,
        )
        time.sleep(DEFAULT_LONG_PRESS_DELAY)

    def swipe(self, start_x: int, start_y: int, end_x: int, end_y: int) -> None:
        dist_sq = (start_x - end_x) ** 2 + (start_y - end_y) ** 2
        duration_ms = int(dist_sq / 1000)
        duration_ms = max(100, min(duration_ms, 2000))
        subprocess.run(
            self._p()
            + [
                "shell",
                "input",
                "swipe",
                str(start_x),
                str(start_y),
                str(end_x),
                str(end_y),
                str(duration_ms),
            ],
            capture_output=True,
        )
        time.sleep(DEFAULT_SWIPE_DELAY)

    def back(self) -> None:
        subprocess.run(self._p() + ["shell", "input", "keyevent", "4"], capture_output=True)
        time.sleep(DEFAULT_BACK_DELAY)

    def home(self) -> None:
        subprocess.run(
            self._p() + ["shell", "input", "keyevent", "KEYCODE_HOME"],
            capture_output=True,
        )
        time.sleep(DEFAULT_HOME_DELAY)

    def detect_and_set_adb_keyboard(self) -> str:
        result = subprocess.run(
            self._p() + ["shell", "settings", "get", "secure", "default_input_method"],
            capture_output=True,
            text=True,
        )
        current = (result.stdout + result.stderr).strip()
        if "com.android.adbkeyboard/.AdbIME" not in current:
            subprocess.run(
                self._p() + ["shell", "ime", "set", "com.android.adbkeyboard/.AdbIME"],
                capture_output=True,
                text=True,
            )
        self.type_text("")
        return current

    def restore_keyboard(self, ime: str) -> None:
        subprocess.run(self._p() + ["shell", "ime", "set", ime], capture_output=True, text=True)

    def clear_text(self) -> None:
        subprocess.run(
            self._p() + ["shell", "am", "broadcast", "-a", "ADB_CLEAR_TEXT"],
            capture_output=True,
            text=True,
        )

    def type_text(self, text: str) -> None:
        encoded = base64.b64encode(text.encode("utf-8")).decode("utf-8")
        subprocess.run(
            self._p()
            + ["shell", "am", "broadcast", "-a", "ADB_INPUT_B64", "--es", "msg", encoded],
            capture_output=True,
            text=True,
        )


def _fallback(sensitive: bool = False) -> Screenshot:
    w, h = 1080, 2400
    black = Image.new("RGB", (w, h), color="black")
    buf = BytesIO()
    black.save(buf, format="PNG")
    return Screenshot(
        base64_data=base64.b64encode(buf.getvalue()).decode("utf-8"),
        width=w,
        height=h,
        is_sensitive=sensitive,
    )
