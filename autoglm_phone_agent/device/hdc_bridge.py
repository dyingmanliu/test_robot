# SPDX-License-Identifier: Apache-2.0
# Patterns adapted from Open-AutoGLM phone_agent/hdc/

from __future__ import annotations

import base64
import os
import re
import subprocess
import tempfile
import time
import uuid
from io import BytesIO

from PIL import Image

from autoglm_phone_agent.config.apps_harmonyos import APP_ABILITIES, APP_PACKAGES
from autoglm_phone_agent.config.timing import (
    DEFAULT_BACK_DELAY,
    DEFAULT_DOUBLE_TAP_DELAY,
    DEFAULT_HOME_DELAY,
    DEFAULT_LAUNCH_DELAY,
    DEFAULT_LONG_PRESS_DELAY,
    DEFAULT_SWIPE_DELAY,
    DEFAULT_TAP_DELAY,
)
from autoglm_phone_agent.device.adb_bridge import Screenshot, _fallback
from autoglm_phone_agent.device.hdc_resolve import resolve_hdc_executable


class HdcBridge:
    """HarmonyOS device control via HDC + uitest uiInput (Open-AutoGLM compatible)."""

    uses_native_input = True

    def __init__(self, device_id: str | None = None, hdc_home: str | None = None) -> None:
        self.device_id = device_id
        self.hdc_home = hdc_home or os.getenv("HDC_HOME")
        self._hdc_bin = resolve_hdc_executable(self.hdc_home)

    def _prefix(self) -> list[str]:
        cmd = [self._hdc_bin]
        if self.device_id:
            cmd.extend(["-t", self.device_id])
        return cmd

    def _run(
        self,
        args: list[str],
        *,
        timeout: int = 25,
        text: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        env = {**os.environ}
        if self.hdc_home:
            env["HDC_HOME"] = self.hdc_home
        return subprocess.run(
            self._prefix() + args,
            capture_output=True,
            text=text,
            timeout=timeout,
            env=env,
        )

    def get_current_app(self) -> str:
        result = self._run(["shell", "aa", "dump", "-l"], timeout=30)
        output = result.stdout or ""
        if not output:
            return "System Home"

        lines = output.split("\n")
        foreground_bundle: str | None = None
        current_bundle: str | None = None

        for line in lines:
            if "app name [" in line:
                match = re.search(r"\[([^\]]+)\]", line)
                if match:
                    current_bundle = match.group(1)
            if "state #FOREGROUND" in line or "state #foreground" in line.lower():
                if current_bundle:
                    foreground_bundle = current_bundle
                    break
            if "Mission ID" in line:
                current_bundle = None

        if foreground_bundle:
            for app_name, package in APP_PACKAGES.items():
                if package == foreground_bundle:
                    return app_name
            return foreground_bundle
        return "System Home"

    def get_screenshot(self, timeout: int = 10) -> Screenshot:
        temp_path = os.path.join(tempfile.gettempdir(), f"hdc_screen_{uuid.uuid4().hex}.png")
        remote = f"/data/local/tmp/tmp_autoglm_{uuid.uuid4().hex[:12]}.jpeg"
        try:
            result = self._run(
                ["shell", "screenshot", remote],
                timeout=timeout,
            )
            out = (result.stdout or "") + (result.stderr or "")
            if any(x in out.lower() for x in ("fail", "error", "not found")):
                result = self._run(
                    ["shell", "snapshot_display", "-f", remote],
                    timeout=timeout,
                )
                out = (result.stdout or "") + (result.stderr or "")
                if any(x in out.lower() for x in ("fail", "error")):
                    return _fallback(True)

            recv = self._run(["file", "recv", remote, temp_path], timeout=10)
            if recv.returncode != 0 or not os.path.isfile(temp_path):
                return _fallback(False)

            with Image.open(temp_path) as img:
                width, height = img.size
                buf = BytesIO()
                img.save(buf, format="PNG")
                b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            os.remove(temp_path)
            return Screenshot(base64_data=b64, width=width, height=height, is_sensitive=False)
        except Exception as e:
            print(f"HDC screenshot error: {e}")
            return _fallback(False)
        finally:
            try:
                self._run(["shell", "rm", "-f", remote], timeout=8)
            except Exception:
                pass

    def launch_app(self, app_name: str) -> bool:
        if app_name not in APP_PACKAGES:
            return False
        bundle = APP_PACKAGES[app_name]
        ability = APP_ABILITIES.get(bundle, "EntryAbility")
        self._run(
            ["shell", "aa", "start", "-b", bundle, "-a", ability],
            timeout=20,
        )
        time.sleep(DEFAULT_LAUNCH_DELAY)
        return True

    def tap(self, x: int, y: int) -> None:
        self._run(["shell", "uitest", "uiInput", "click", str(x), str(y)])
        time.sleep(DEFAULT_TAP_DELAY)

    def double_tap(self, x: int, y: int) -> None:
        self._run(["shell", "uitest", "uiInput", "doubleClick", str(x), str(y)])
        time.sleep(DEFAULT_DOUBLE_TAP_DELAY)

    def long_press(self, x: int, y: int, duration_ms: int = 3000) -> None:
        _ = duration_ms
        self._run(["shell", "uitest", "uiInput", "longClick", str(x), str(y)])
        time.sleep(DEFAULT_LONG_PRESS_DELAY)

    def swipe(self, start_x: int, start_y: int, end_x: int, end_y: int) -> None:
        dist_sq = (start_x - end_x) ** 2 + (start_y - end_y) ** 2
        duration_ms = max(500, min(int(dist_sq / 1000), 1000))
        self._run(
            [
                "shell",
                "uitest",
                "uiInput",
                "swipe",
                str(start_x),
                str(start_y),
                str(end_x),
                str(end_y),
                str(duration_ms),
            ]
        )
        time.sleep(DEFAULT_SWIPE_DELAY)

    def back(self) -> None:
        self._run(["shell", "uitest", "uiInput", "keyEvent", "Back"])
        time.sleep(DEFAULT_BACK_DELAY)

    def home(self) -> None:
        self._run(["shell", "uitest", "uiInput", "keyEvent", "Home"])
        time.sleep(DEFAULT_HOME_DELAY)

    def detect_and_set_adb_keyboard(self) -> str:
        """鸿蒙使用原生 uitest 输入，无需 ADB Keyboard。"""
        return ""

    def restore_keyboard(self, ime: str) -> None:
        if not ime:
            return
        try:
            self._run(["shell", "ime", "set", ime], timeout=10)
        except Exception:
            pass

    def clear_text(self) -> None:
        try:
            self._run(["shell", "uitest", "uiInput", "keyEvent", "2072", "2017"])
            self._run(["shell", "uitest", "uiInput", "keyEvent", "2055"])
        except Exception:
            pass

    def type_text(self, text: str) -> None:
        if "\n" in text:
            lines = text.split("\n")
            for i, line in enumerate(lines):
                if line:
                    escaped = line.replace('"', '\\"').replace("$", "\\$")
                    self._run(["shell", "uitest", "uiInput", "text", escaped])
                if i < len(lines) - 1:
                    self._run(["shell", "uitest", "uiInput", "keyEvent", "2054"])
        else:
            escaped = text.replace('"', '\\"').replace("$", "\\$")
            self._run(["shell", "uitest", "uiInput", "text", escaped])
