# SPDX-License-Identifier: Apache-2.0
# Grounding client aligned with Tongyi-MAI/MAI-UI mai_grounding_agent.py

from __future__ import annotations

import base64
import json
import logging
import re
import sys
import time
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from openai import APIStatusError, OpenAI
from PIL import Image

from mai_ui_agent.config import MaiUiConfig, load_config
from mai_ui_agent.coords import SCALE_FACTOR, norm999_to_norm1000, norm_to_pixel
from mai_ui_agent.prompt import MAI_MOBILE_SYS_PROMPT_GROUNDING

_llm_logger = logging.getLogger("mai_ui.llm")


def _estimate_tokens(text: str) -> int:
    s = (text or "").strip()
    if not s:
        return 0
    total = 0.0
    for ch in s:
        total += 1.2 if ord(ch) > 127 else 0.25
    return max(0, int(round(total)))


def parse_grounding_response(text: str) -> dict[str, Any]:
    text = text.strip()
    result: dict[str, Any] = {"thinking": None, "coordinate": None}

    think_match = re.search(r"<grounding_think>(.*?)</grounding_think>", text, re.DOTALL)
    if think_match:
        result["thinking"] = think_match.group(1).strip()

    answer_match = re.search(r"<answer>(.*?)</answer>", text, re.DOTALL)
    if not answer_match:
        raise ValueError("模型输出中未找到 <answer> 块")
    answer_text = answer_match.group(1).strip()
    answer_json = json.loads(answer_text)
    coordinates = answer_json.get("coordinate", [])
    if len(coordinates) != 2:
        raise ValueError(f"coordinate 应为 2 个值，实际为 {len(coordinates)}")
    point_x = coordinates[0] / SCALE_FACTOR
    point_y = coordinates[1] / SCALE_FACTOR
    result["coordinate"] = [point_x, point_y]
    return result


def pil_to_base64(image: Image.Image) -> str:
    buf = BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def load_image(path: str | Path) -> Image.Image:
    img = Image.open(path)
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


def _mlx_vlm_available() -> bool:
    if sys.version_info < (3, 10):
        return False
    try:
        import mlx_vlm  # noqa: F401

        return True
    except ImportError:
        return False


def _should_use_mlx(config: MaiUiConfig) -> bool:
    if config.backend == "mlx_vlm":
        return True
    if config.backend == "openai":
        return False
    if not _mlx_vlm_available():
        return False
    try:
        from mai_ui_agent.mlx_inference import resolve_mlx_model_path

        resolve_mlx_model_path(config)
        return True
    except FileNotFoundError:
        return False


@dataclass
class GroundingResult:
    instruction: str
    raw_text: str
    thinking: str | None
    coordinate_norm: tuple[float, float] | None
    coordinate_999: tuple[int, int] | None
    coordinate_1000: tuple[int, int] | None
    coordinate_px: tuple[int, int] | None
    image_width: int
    image_height: int
    ok: bool
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "instruction": self.instruction,
            "ok": self.ok,
            "error": self.error,
            "thinking": self.thinking,
            "coordinate_norm": list(self.coordinate_norm) if self.coordinate_norm else None,
            "coordinate_999": list(self.coordinate_999) if self.coordinate_999 else None,
            "coordinate_1000": list(self.coordinate_1000) if self.coordinate_1000 else None,
            "coordinate_px": list(self.coordinate_px) if self.coordinate_px else None,
            "image_width": self.image_width,
            "image_height": self.image_height,
            "raw_text": self.raw_text,
        }


class MaiUiGroundingAgent:
    """截图 + 指令 → UI 元素坐标（mlx_vlm 本地推理或 OpenAI 兼容 API）。"""

    def __init__(self, config: MaiUiConfig | None = None) -> None:
        self.config = config or load_config()
        self._client: OpenAI | None = None
        if not _should_use_mlx(self.config):
            self._client = OpenAI(
                base_url=self.config.base_url.rstrip("/"),
                api_key=self.config.api_key or "empty",
            )

    def _build_openai_messages(
        self, instruction: str, image: Image.Image
    ) -> list[dict[str, Any]]:
        encoded = pil_to_base64(image)
        return [
            {
                "role": "system",
                "content": [{"type": "text", "text": MAI_MOBILE_SYS_PROMPT_GROUNDING}],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{encoded}"},
                    },
                    {"type": "text", "text": instruction},
                ],
            },
        ]

    def _predict_openai(self, instruction: str, image: Image.Image) -> str:
        if self._client is None:
            self._client = OpenAI(
                base_url=self.config.base_url.rstrip("/"),
                api_key=self.config.api_key or "empty",
            )
        messages = self._build_openai_messages(instruction, image)
        last_err: Exception | None = None
        for attempt in range(self.config.max_retries):
            try:
                kwargs: dict[str, Any] = {
                    "model": self.config.model_name,
                    "messages": messages,
                    "max_tokens": self.config.max_tokens,
                    "temperature": self.config.temperature,
                    "top_p": self.config.top_p,
                }
                if self.config.top_k >= 0:
                    kwargs["extra_body"] = {
                        "repetition_penalty": 1.0,
                        "top_k": self.config.top_k,
                    }
                t0 = time.perf_counter()
                response = self._client.chat.completions.create(**kwargs)
                duration_ms = int((time.perf_counter() - t0) * 1000)
                content = (response.choices[0].message.content or "").strip()
                usage = getattr(response, "usage", None)
                if usage is not None:
                    pt = getattr(usage, "prompt_tokens", None)
                    ct = getattr(usage, "completion_tokens", None)
                    tt = getattr(usage, "total_tokens", None)
                    _llm_logger.info(
                        "[mai_ui/openai] grounding %sms tokens=%s prompt=%s completion=%s model=%s",
                        duration_ms,
                        tt,
                        pt,
                        ct,
                        self.config.model_name,
                    )
                else:
                    pt = _estimate_tokens(instruction)
                    ct = _estimate_tokens(content)
                    _llm_logger.info(
                        "[mai_ui/openai] grounding %sms tokens=%s (估算) prompt=%s completion=%s model=%s",
                        duration_ms,
                        pt + ct,
                        pt,
                        ct,
                        self.config.model_name,
                    )
                return content
            except Exception as e:
                last_err = e
                if self.config.verbose:
                    print(f"[mai_ui] openai attempt {attempt + 1} failed: {e}")
        raise RuntimeError(
            f"OpenAI 兼容 API 调用失败（已重试 {self.config.max_retries} 次）: {last_err}"
        )

    def _predict_mlx(self, instruction: str, image: Image.Image) -> str:
        from mai_ui_agent.mlx_inference import predict_mlx

        return predict_mlx(instruction, image, self.config)

    def predict(self, instruction: str, image: Image.Image) -> tuple[str, dict[str, Any]]:
        use_mlx = _should_use_mlx(self.config)
        last_err: Exception | None = None

        if use_mlx:
            try:
                prediction = self._predict_mlx(instruction, image)
                if self.config.verbose:
                    print(f"[mai_ui] raw response (mlx_vlm):\n{prediction}\n")
                return prediction, parse_grounding_response(prediction)
            except Exception as e:
                last_err = e
                if self.config.backend == "mlx_vlm":
                    raise RuntimeError(
                        f"MAI-UI mlx_vlm 推理失败: {last_err}"
                    ) from e
                if self.config.verbose:
                    print(f"[mai_ui] mlx_vlm failed, fallback to openai: {e}")

        for attempt in range(self.config.max_retries):
            try:
                prediction = self._predict_openai(instruction, image)
                if self.config.verbose:
                    print(f"[mai_ui] raw response (openai):\n{prediction}\n")
                return prediction, parse_grounding_response(prediction)
            except APIStatusError as e:
                last_err = e
                if e.status_code and e.status_code >= 500 and _mlx_vlm_available():
                    try:
                        prediction = self._predict_mlx(instruction, image)
                        return prediction, parse_grounding_response(prediction)
                    except Exception as mlx_err:
                        last_err = mlx_err
                if self.config.verbose:
                    print(f"[mai_ui] openai attempt {attempt + 1} failed: {e}")
            except Exception as e:
                last_err = e
                if self.config.verbose:
                    print(f"[mai_ui] openai attempt {attempt + 1} failed: {e}")

        raise RuntimeError(
            f"MAI-UI grounding 调用失败（已重试 {self.config.max_retries} 次）: {last_err}"
        )

    def ground(
        self,
        instruction: str,
        image: Image.Image | str | Path,
    ) -> GroundingResult:
        if isinstance(image, (str, Path)):
            img = load_image(image)
        else:
            img = image
            if img.mode != "RGB":
                img = img.convert("RGB")

        w, h = img.size
        try:
            raw, parsed = self.predict(instruction, img)
            coord = parsed.get("coordinate")
            if not coord:
                return GroundingResult(
                    instruction=instruction,
                    raw_text=raw,
                    thinking=parsed.get("thinking"),
                    coordinate_norm=None,
                    coordinate_999=None,
                    coordinate_1000=None,
                    coordinate_px=None,
                    image_width=w,
                    image_height=h,
                    ok=False,
                    error="未解析到 coordinate",
                )
            xn, yn = float(coord[0]), float(coord[1])
            c999 = (int(round(xn * SCALE_FACTOR)), int(round(yn * SCALE_FACTOR)))
            c1000 = norm999_to_norm1000(c999[0], c999[1])
            px = norm_to_pixel(xn, yn, w, h)
            return GroundingResult(
                instruction=instruction,
                raw_text=raw,
                thinking=parsed.get("thinking"),
                coordinate_norm=(xn, yn),
                coordinate_999=c999,
                coordinate_1000=c1000,
                coordinate_px=px,
                image_width=w,
                image_height=h,
                ok=True,
            )
        except Exception as e:
            return GroundingResult(
                instruction=instruction,
                raw_text="",
                thinking=None,
                coordinate_norm=None,
                coordinate_999=None,
                coordinate_1000=None,
                coordinate_px=None,
                image_width=w,
                image_height=h,
                ok=False,
                error=str(e),
            )
