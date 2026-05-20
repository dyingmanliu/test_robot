# SPDX-License-Identifier: Apache-2.0
# Adapted from Open-AutoGLM phone_agent/actions/handler.py

from __future__ import annotations

import ast
import time
from dataclasses import dataclass
from typing import Any, Callable

from autoglm_phone_tech.config.timing import (
    KEYBOARD_RESTORE_DELAY,
    KEYBOARD_SWITCH_DELAY,
    TEXT_CLEAR_DELAY,
    TEXT_INPUT_DELAY,
)
from autoglm_phone_tech.device.device_factory import DeviceBridge


@dataclass
class ActionResult:
    success: bool
    should_finish: bool
    message: str | None = None
    requires_confirmation: bool = False


class ActionHandler:
    """Executes model actions on an ADB or HDC device bridge."""

    def __init__(
        self,
        device: DeviceBridge,
        confirmation_callback: Callable[[str], bool] | None = None,
        takeover_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.device = device
        self.confirmation_callback = confirmation_callback or self._default_confirmation
        self.takeover_callback = takeover_callback or self._default_takeover

    def execute(self, action: dict[str, Any], screen_width: int, screen_height: int) -> ActionResult:
        meta = action.get("_metadata")
        if meta == "finish":
            return ActionResult(True, True, action.get("message"))
        if meta != "do":
            # 勿结束整条任务：未知 metadata 时继续下一步，由模型重新输出
            return ActionResult(False, False, f"Unknown action metadata: {meta}")

        name = action.get("action")
        handler = self._handlers().get(name)
        if handler is None:
            return ActionResult(False, False, f"Unknown action: {name}")
        try:
            return handler(action, screen_width, screen_height)
        except Exception as e:
            return ActionResult(False, False, f"Action failed: {e}")

    def _handlers(self) -> dict[str, Any]:
        return {
            "Launch": self._launch,
            "Tap": self._tap,
            "Type": self._type,
            "Type_Name": self._type,
            "Swipe": self._swipe,
            "Back": self._back,
            "Home": self._home,
            "Double Tap": self._double_tap,
            "Long Press": self._long_press,
            "Wait": self._wait,
            "Take_over": self._takeover,
            "Note": self._note,
            "Call_API": self._call_api,
            "Interact": self._interact,
        }

    @staticmethod
    def _norm_xy(element: list[int], w: int, h: int) -> tuple[int, int]:
        x = int(element[0] / 1000 * w)
        y = int(element[1] / 1000 * h)
        return x, y

    def _launch(self, action: dict[str, Any], _w: int, _h: int) -> ActionResult:
        app = action.get("app")
        if not app:
            return ActionResult(False, False, "No app name")
        ok = self.device.launch_app(app)
        if ok:
            return ActionResult(True, False)
        return ActionResult(False, False, f"App not in mapping or launch failed: {app}")

    def _tap(self, action: dict[str, Any], w: int, h: int) -> ActionResult:
        el = action.get("element")
        if not el:
            return ActionResult(False, False, "No element coordinates")
        x, y = self._norm_xy(el, w, h)
        if action.get("message") and not self.confirmation_callback(str(action["message"])):
            return ActionResult(False, True, "User cancelled sensitive operation")
        self.device.tap(x, y)
        return ActionResult(True, False)

    def _type(self, action: dict[str, Any], _w: int, _h: int) -> ActionResult:
        text = action.get("text", "")
        if getattr(self.device, "uses_native_input", False):
            self.device.clear_text()
            time.sleep(TEXT_CLEAR_DELAY)
            self.device.type_text(text)
            time.sleep(TEXT_INPUT_DELAY)
            return ActionResult(True, False)
        ime = self.device.detect_and_set_adb_keyboard()
        time.sleep(KEYBOARD_SWITCH_DELAY)
        self.device.clear_text()
        time.sleep(TEXT_CLEAR_DELAY)
        self.device.type_text(text)
        time.sleep(TEXT_INPUT_DELAY)
        self.device.restore_keyboard(ime)
        time.sleep(KEYBOARD_RESTORE_DELAY)
        return ActionResult(True, False)

    def _swipe(self, action: dict[str, Any], w: int, h: int) -> ActionResult:
        start = action.get("start")
        end = action.get("end")
        if not start or not end:
            return ActionResult(False, False, "Missing swipe coordinates")
        sx, sy = self._norm_xy(start, w, h)
        ex, ey = self._norm_xy(end, w, h)
        self.device.swipe(sx, sy, ex, ey)
        return ActionResult(True, False)

    def _back(self, _a: dict[str, Any], _w: int, _h: int) -> ActionResult:
        self.device.back()
        return ActionResult(True, False)

    def _home(self, _a: dict[str, Any], _w: int, _h: int) -> ActionResult:
        self.device.home()
        return ActionResult(True, False)

    def _double_tap(self, action: dict[str, Any], w: int, h: int) -> ActionResult:
        el = action.get("element")
        if not el:
            return ActionResult(False, False, "No element coordinates")
        x, y = self._norm_xy(el, w, h)
        self.device.double_tap(x, y)
        return ActionResult(True, False)

    def _long_press(self, action: dict[str, Any], w: int, h: int) -> ActionResult:
        el = action.get("element")
        if not el:
            return ActionResult(False, False, "No element coordinates")
        x, y = self._norm_xy(el, w, h)
        self.device.long_press(x, y)
        return ActionResult(True, False)

    def _wait(self, action: dict[str, Any], _w: int, _h: int) -> ActionResult:
        duration_str = action.get("duration", "1 seconds")
        try:
            duration = float(duration_str.replace("seconds", "").strip())
        except ValueError:
            duration = 1.0
        time.sleep(duration)
        return ActionResult(True, False)

    def _takeover(self, action: dict[str, Any], _w: int, _h: int) -> ActionResult:
        self.takeover_callback(action.get("message", "需要人工协助"))
        return ActionResult(True, False)

    def _note(self, _action: dict[str, Any], _w: int, _h: int) -> ActionResult:
        return ActionResult(True, False)

    def _call_api(self, _action: dict[str, Any], _w: int, _h: int) -> ActionResult:
        return ActionResult(True, False)

    def _interact(self, _action: dict[str, Any], _w: int, _h: int) -> ActionResult:
        return ActionResult(True, False, message="User interaction required")

    @staticmethod
    def _default_confirmation(message: str) -> bool:
        response = input(f"敏感操作: {message}\n确认执行? (Y/N): ")
        return response.strip().upper() == "Y"

    @staticmethod
    def _default_takeover(message: str) -> None:
        input(f"{message}\n完成后按 Enter 继续…")


def parse_action(response: str) -> dict[str, Any]:
    """Parse ``do(...)`` / ``finish(...)`` from model output (Open-AutoGLM protocol)."""
    response = response.strip()
    if response.startswith('do(action="Type"') or response.startswith('do(action="Type_Name"'):
        text = response.split("text=", 1)[1][1:-2]
        return {"_metadata": "do", "action": "Type", "text": text}
    if response.startswith("do"):
        try:
            normalized = (
                response.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
            )
            tree = ast.parse(normalized, mode="eval")
            if not isinstance(tree.body, ast.Call):
                raise ValueError("Expected a function call")
            call = tree.body
            action: dict[str, Any] = {"_metadata": "do"}
            for kw in call.keywords:
                if kw.arg:
                    action[kw.arg] = ast.literal_eval(kw.value)
            return action
        except (SyntaxError, ValueError) as e:
            raise ValueError(f"Failed to parse do() action: {e}") from e
    if response.startswith("finish"):
        return {
            "_metadata": "finish",
            "message": response.replace("finish(message=", "", 1)[1:-2],
        }
    raise ValueError(f"Failed to parse action: {response}")
