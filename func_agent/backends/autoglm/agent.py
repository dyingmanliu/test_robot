"""Orchestrates the observe -> plan -> act loop for APP automation testing."""

from __future__ import annotations

import json
import traceback
from dataclasses import dataclass
from typing import Any, Callable, Optional

from autoglm_phone_agent.actions.handler import ActionHandler, parse_action
from autoglm_phone_agent.config import get_system_prompt
from autoglm_phone_agent.device.device_factory import DeviceBridge, create_device
from autoglm_phone_agent.device.platform import DevicePlatform
from autoglm_phone_agent.model.client import MessageBuilder, ModelClient, ModelConfig


@dataclass
class AgentConfig:
    max_steps: int = 100
    device_id: str | None = None
    device_platform: str = "android"
    lang: str = "cn"
    system_prompt: str | None = None
    verbose: bool = True

    def __post_init__(self) -> None:
        if self.system_prompt is None:
            self.system_prompt = get_system_prompt(self.lang)

    @property
    def platform(self) -> DevicePlatform:
        return DevicePlatform.parse(self.device_platform)


@dataclass
class StepResult:
    success: bool
    finished: bool
    action: dict[str, Any] | None
    thinking: str
    message: str | None = None


@dataclass
class AgentRunOutcome:
    ok: bool
    message: str


class PhoneTestAgent:
    def __init__(
        self,
        model_config: ModelConfig | None = None,
        agent_config: AgentConfig | None = None,
        device: DeviceBridge | None = None,
        confirmation_callback: Callable[[str], bool] | None = None,
        takeover_callback: Callable[[str], None] | None = None,
        print_model_stream: bool = False,
    ) -> None:
        self.model_config = model_config or ModelConfig()
        self.agent_config = agent_config or AgentConfig()
        self.device = device or create_device(
            self.agent_config.platform,
            device_id=self.agent_config.device_id,
        )
        self.model_client = ModelClient(self.model_config, print_stream=print_model_stream)
        self.action_handler = ActionHandler(
            self.device,
            confirmation_callback=confirmation_callback,
            takeover_callback=takeover_callback,
        )
        self._context: list[dict[str, Any]] = []
        self._step_count = 0

    def reset(self) -> None:
        self._context = []
        self._step_count = 0

    def run(
        self,
        task: str,
        *,
        on_step: Optional[Callable[[int, StepResult], None]] = None,
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> AgentRunOutcome:
        self.reset()
        first = self._execute_step(task, is_first=True)
        if on_step:
            on_step(self._step_count, first)
        if first.finished:
            msg = first.message or "任务结束"
            return AgentRunOutcome(first.success, msg)
        while self._step_count < self.agent_config.max_steps:
            if should_cancel and should_cancel():
                return AgentRunOutcome(False, "执行已取消")
            step = self._execute_step(is_first=False)
            if on_step:
                on_step(self._step_count, step)
            if step.finished:
                msg = step.message or "任务结束"
                return AgentRunOutcome(step.success, msg)
        return AgentRunOutcome(False, "已达到最大步数限制")

    def _execute_step(self, user_prompt: str | None = None, is_first: bool = False) -> StepResult:
        self._step_count += 1
        screenshot = self.device.get_screenshot()
        current_app = self.device.get_current_app()
        if is_first:
            self._context.append(MessageBuilder.create_system_message(self.agent_config.system_prompt or ""))
            screen_info = MessageBuilder.build_screen_info(current_app)
            text_content = f"{user_prompt}\n\n{screen_info}"
            self._context.append(
                MessageBuilder.create_user_message(text=text_content, image_base64=screenshot.base64_data)
            )
        else:
            screen_info = MessageBuilder.build_screen_info(current_app)
            text_content = f"** Screen Info **\n\n{screen_info}"
            self._context.append(
                MessageBuilder.create_user_message(text=text_content, image_base64=screenshot.base64_data)
            )
        try:
            response = self.model_client.request(self._context)
        except Exception as e:
            if self.agent_config.verbose:
                traceback.print_exc()
            return StepResult(False, True, None, "", f"模型调用失败: {e}")
        raw_action = response.action
        parse_fallback_note: str | None = None
        try:
            action = parse_action(raw_action)
        except ValueError:
            if self.agent_config.verbose:
                traceback.print_exc()
            parse_fallback_note = (
                "模型动作无法解析为 do()/finish()，已自动等待 2 秒后重试。"
                f" 原始片段: {raw_action[:500]}{'…' if len(raw_action) > 500 else ''}"
            )
            action = {"_metadata": "do", "action": "Wait", "duration": "2 seconds"}
        self._context[-1] = MessageBuilder.remove_images_from_message(self._context[-1])
        try:
            result = self.action_handler.execute(action, screenshot.width, screenshot.height)
        except Exception as e:
            if self.agent_config.verbose:
                traceback.print_exc()
            result = self.action_handler.execute(
                {"_metadata": "do", "action": "Wait", "duration": "2 seconds"},
                screenshot.width,
                screenshot.height,
            )
            parse_fallback_note = (parse_fallback_note or "") + f"\n动作执行异常（已等待后继续）: {e}"
        assistant_text = f"{response.thinking} {raw_action}".strip()
        self._context.append(MessageBuilder.create_assistant_message(assistant_text))
        finished = action.get("_metadata") == "finish" or result.should_finish
        msg_parts = [result.message, action.get("message"), parse_fallback_note]
        combined_msg = "\n".join(p for p in msg_parts if p)
        return StepResult(
            success=result.success,
            finished=bool(finished),
            action=action,
            thinking=response.thinking,
            message=combined_msg or None,
        )
