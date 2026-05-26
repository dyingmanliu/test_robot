# SPDX-License-Identifier: Apache-2.0
# Adapted from Open-AutoGLM phone_agent/model/client.py

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

_llm_logger = logging.getLogger("app.llm")


@dataclass
class ModelConfig:
    base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    api_key: str = ""
    model_name: str = "autoglm-phone"
    max_tokens: int = 3000
    temperature: float = 0.0
    top_p: float = 0.85
    frequency_penalty: float = 0.2
    extra_body: dict[str, Any] = field(default_factory=dict)
    lang: str = "cn"


@dataclass
class ModelResponse:
    thinking: str
    action: str
    raw_content: str
    time_to_first_token: float | None = None
    time_to_thinking_end: float | None = None
    total_time: float | None = None


class ModelClient:
    """OpenAI-compatible streaming client for AutoGLM-Phone."""

    def __init__(self, config: ModelConfig | None = None, print_stream: bool = False) -> None:
        self.config = config or ModelConfig()
        self.print_stream = print_stream
        self.client = OpenAI(base_url=self.config.base_url, api_key=self.config.api_key)

    def request(self, messages: list[dict[str, Any]]) -> ModelResponse:
        start_time = time.time()
        time_to_first_token: float | None = None
        time_to_thinking_end: float | None = None

        timeout_sec = float(os.getenv("PHONE_AGENT_TIMEOUT_SEC", "120"))
        stream = self.client.chat.completions.create(
            messages=messages,
            model=self.config.model_name,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            top_p=self.config.top_p,
            frequency_penalty=self.config.frequency_penalty,
            extra_body=self.config.extra_body,
            stream=True,
            timeout=timeout_sec,
        )

        raw_content = ""
        buffer = ""
        action_markers = ["finish(message=", "do(action="]
        in_action_phase = False
        first_token_received = False

        for chunk in stream:
            if len(chunk.choices) == 0:
                continue
            if chunk.choices[0].delta.content is not None:
                content = chunk.choices[0].delta.content
                raw_content += content

                if not first_token_received:
                    time_to_first_token = time.time() - start_time
                    first_token_received = True

                if in_action_phase:
                    continue

                buffer += content
                marker_found = False
                for marker in action_markers:
                    if marker in buffer:
                        thinking_part = buffer.split(marker, 1)[0]
                        if self.print_stream:
                            print(thinking_part, end="", flush=True)
                            print()
                        in_action_phase = True
                        marker_found = True
                        if time_to_thinking_end is None:
                            time_to_thinking_end = time.time() - start_time
                        break

                if marker_found:
                    continue

                is_potential_marker = False
                for marker in action_markers:
                    for i in range(1, len(marker)):
                        if buffer.endswith(marker[:i]):
                            is_potential_marker = True
                            break
                    if is_potential_marker:
                        break

                if not is_potential_marker and self.print_stream:
                    print(buffer, end="", flush=True)
                    buffer = ""

        total_time = time.time() - start_time
        thinking, action = self._parse_response(raw_content)

        est_prompt = sum(
            len(str(m.get("content", ""))) for m in messages
        )
        est_pt = max(1, est_prompt // 3)
        est_ct = max(1, len(raw_content) // 2)
        _llm_logger.info(
            "[autoglm] chat.completions stream %sms tokens≈%s (估算) prompt≈%s completion≈%s model=%s",
            int(total_time * 1000),
            est_pt + est_ct,
            est_pt,
            est_ct,
            self.config.model_name,
        )

        if self.print_stream:
            print()
            print("=" * 50)
            print(f"首 token: {time_to_first_token:.3f}s  |  推理结束: {time_to_thinking_end}  |  总耗时: {total_time:.3f}s")
            print("=" * 50)

        return ModelResponse(
            thinking=thinking,
            action=action,
            raw_content=raw_content,
            time_to_first_token=time_to_first_token,
            time_to_thinking_end=time_to_thinking_end,
            total_time=total_time,
        )

    def _parse_response(self, content: str) -> tuple[str, str]:
        if "finish(message=" in content:
            parts = content.split("finish(message=", 1)
            return parts[0].strip(), "finish(message=" + parts[1]
        if "do(action=" in content:
            parts = content.split("do(action=", 1)
            return parts[0].strip(), "do(action=" + parts[1]
        return "", content


class MessageBuilder:
    @staticmethod
    def create_system_message(content: str) -> dict[str, Any]:
        return {"role": "system", "content": content}

    @staticmethod
    def create_user_message(text: str, image_base64: str | None = None) -> dict[str, Any]:
        content: list[dict[str, Any]] = []
        if image_base64:
            content.append(
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
            )
        content.append({"type": "text", "text": text})
        return {"role": "user", "content": content}

    @staticmethod
    def create_assistant_message(content: str) -> dict[str, Any]:
        return {"role": "assistant", "content": content}

    @staticmethod
    def remove_images_from_message(message: dict[str, Any]) -> dict[str, Any]:
        if isinstance(message.get("content"), list):
            message["content"] = [item for item in message["content"] if item.get("type") == "text"]
        return message

    @staticmethod
    def build_screen_info(current_app: str, **extra_info: Any) -> str:
        info = {"current_app": current_app, **extra_info}
        return json.dumps(info, ensure_ascii=False)
