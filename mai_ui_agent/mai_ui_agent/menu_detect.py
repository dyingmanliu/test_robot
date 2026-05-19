# SPDX-License-Identifier: Apache-2.0
"""一次性识别截图中当前页面的全部导航菜单（含顶部、底部等）。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image

from mai_ui_agent.config import MaiUiConfig, load_config
from mai_ui_agent.coords import SCALE_FACTOR, norm999_to_norm1000, norm_to_pixel
from mai_ui_agent.grounding import load_image
from mai_ui_agent.prompt import (
    MAI_MOBILE_SYS_PROMPT_MENU_DETECT,
    MENU_DETECT_USER_INSTRUCTION,
)

_MENU_DETECT_MAX_TOKENS = 2048
_RETRY_USER_INSTRUCTION = (
    "仅输出一个 <answer> 块，内容为合法 JSON，不要 Markdown，不要其它文字。"
    '格式: <answer>{"menus":[{"name":"名称","region":"top","coordinate":[x,y]}]}</answer>'
)


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _repair_json(text: str) -> str:
    text = re.sub(r",\s*([}\]])", r"\1", text)
    text = text.replace("'", '"')
    return text


def _try_parse_json_object(text: str) -> dict[str, Any] | None:
    text = _strip_code_fence(text.strip())
    if not text:
        return None
    for candidate in (text, _repair_json(text)):
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
        if isinstance(data, list):
            return {"menus": data}
    return None


def _extract_menus_array_from_text(text: str) -> list[dict[str, Any]] | None:
    patterns = [
        r'"menus"\s*:\s*(\[[\s\S]*?\])',
        r"'menus'\s*:\s*(\[[\s\S]*?\])",
        r"menus\s*=\s*(\[[\s\S]*?\])",
    ]
    for pat in patterns:
        match = re.search(pat, text, re.DOTALL | re.IGNORECASE)
        if not match:
            continue
        arr_text = match.group(1).strip()
        for candidate in (arr_text, _repair_json(arr_text)):
            try:
                data = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(data, list):
                return [x for x in data if isinstance(x, dict)]
    return None


def _extract_menu_objects_loose(text: str) -> list[dict[str, Any]]:
    """从非标准输出中抽取含 name + coordinate 的对象。"""
    menus: list[dict[str, Any]] = []
    obj_pattern = re.compile(
        r"\{[^{}]*?(?:\"|')name(?:\"|')\s*:\s*(?:\"|')([^\"']+)(?:\"|')"
        r"[^{}]*?(?:\"|')coordinate(?:\"|')\s*:\s*\[\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*\]"
        r"[^{}]*?\}",
        re.DOTALL | re.IGNORECASE,
    )
    for match in obj_pattern.finditer(text):
        name, x, y = match.group(1), match.group(2), match.group(3)
        entry: dict[str, Any] = {
            "name": name.strip(),
            "coordinate": [int(float(x)), int(float(y))],
        }
        region_match = re.search(
            r"(?:\"|')region(?:\"|')\s*:\s*(?:\"|')([^\"']+)(?:\"|')",
            match.group(0),
            re.IGNORECASE,
        )
        if region_match:
            entry["region"] = region_match.group(1).strip()
        menus.append(entry)
    return menus


def _extract_answer_json(text: str) -> dict[str, Any]:
    text = text.strip()
    candidates: list[str] = []

    for match in re.finditer(r"<answer>(.*?)</answer>", text, re.DOTALL | re.IGNORECASE):
        candidates.append(match.group(1).strip())

    for match in re.finditer(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE):
        candidates.append(match.group(1).strip())

    candidates.append(text)

    for raw in candidates:
        parsed = _try_parse_json_object(raw)
        if parsed is not None:
            return parsed

    menus = _extract_menus_array_from_text(text)
    if menus is not None:
        return {"menus": menus}

    loose = _extract_menu_objects_loose(text)
    if loose:
        return {"menus": loose}

    snippet = text[:400].replace("\n", " ")
    raise ValueError(f"模型输出中未找到可解析的 JSON（片段: {snippet!r}…）")


def parse_menu_detect_response(text: str) -> tuple[str | None, list[dict[str, Any]]]:
    think_match = re.search(r"<grounding_think>(.*?)</grounding_think>", text, re.DOTALL)
    thinking = think_match.group(1).strip() if think_match else None
    data = _extract_answer_json(text)
    menus = data.get("menus")
    if menus is None:
        menus = data.get("menu_items") or data.get("items") or []
    if not isinstance(menus, list):
        raise ValueError("menus 字段应为数组")
    return thinking, menus


@dataclass
class MenuItemResult:
    name: str
    region: str | None
    raw_text: str
    thinking: str | None
    coordinate_norm: tuple[float, float] | None
    coordinate_999: tuple[int, int] | None
    coordinate_1000: tuple[int, int] | None
    coordinate_px: tuple[int, int] | None
    ok: bool
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "region": self.region,
            "ok": self.ok,
            "error": self.error,
            "coordinate_norm": list(self.coordinate_norm) if self.coordinate_norm else None,
            "coordinate_999": list(self.coordinate_999) if self.coordinate_999 else None,
            "coordinate_1000": list(self.coordinate_1000) if self.coordinate_1000 else None,
            "coordinate_px": list(self.coordinate_px) if self.coordinate_px else None,
        }


@dataclass
class MenuDetectResult:
    image_width: int
    image_height: int
    raw_text: str
    thinking: str | None
    menus: list[MenuItemResult]
    ok: bool
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "error": self.error,
            "image_width": self.image_width,
            "image_height": self.image_height,
            "thinking": self.thinking,
            "raw_text": self.raw_text,
            "menus": [m.to_dict() for m in self.menus],
        }


def _normalize_region(raw: Any) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip().lower()
    mapping = {
        "top": "top",
        "顶部": "top",
        "header": "top",
        "navbar": "top",
        "bottom": "bottom",
        "底部": "bottom",
        "tabbar": "bottom",
        "left": "left",
        "左侧": "left",
        "right": "right",
        "右侧": "right",
        "other": "other",
        "其他": "other",
    }
    return mapping.get(s, s if s in ("top", "bottom", "left", "right", "other") else "other")


def _menu_item_from_raw(
    entry: dict[str, Any],
    image_w: int,
    image_h: int,
) -> MenuItemResult:
    name = str(entry.get("name") or entry.get("label") or entry.get("text") or "").strip()
    region = _normalize_region(
        entry.get("region") or entry.get("area") or entry.get("position")
    )
    if not name:
        return MenuItemResult(
            name="",
            region=region,
            raw_text="",
            thinking=None,
            coordinate_norm=None,
            coordinate_999=None,
            coordinate_1000=None,
            coordinate_px=None,
            ok=False,
            error="缺少菜单名称",
        )
    coord = entry.get("coordinate") or entry.get("coords") or entry.get("point")
    if not isinstance(coord, (list, tuple)) or len(coord) != 2:
        return MenuItemResult(
            name=name,
            region=region,
            raw_text="",
            thinking=None,
            coordinate_norm=None,
            coordinate_999=None,
            coordinate_1000=None,
            coordinate_px=None,
            ok=False,
            error="coordinate 无效",
        )
    try:
        xn = float(coord[0]) / SCALE_FACTOR
        yn = float(coord[1]) / SCALE_FACTOR
        c999 = (int(round(xn * SCALE_FACTOR)), int(round(yn * SCALE_FACTOR)))
        c1000 = norm999_to_norm1000(c999[0], c999[1])
        px = norm_to_pixel(xn, yn, image_w, image_h)
        if region is None and px:
            _, py = px
            if py < image_h * 0.2:
                region = "top"
            elif py > image_h * 0.8:
                region = "bottom"
        return MenuItemResult(
            name=name,
            region=region,
            raw_text="",
            thinking=None,
            coordinate_norm=(xn, yn),
            coordinate_999=c999,
            coordinate_1000=c1000,
            coordinate_px=px,
            ok=True,
        )
    except (TypeError, ValueError) as e:
        return MenuItemResult(
            name=name,
            region=region,
            raw_text="",
            thinking=None,
            coordinate_norm=None,
            coordinate_999=None,
            coordinate_1000=None,
            coordinate_px=None,
            ok=False,
            error=str(e),
        )


class MaiUiMenuDetectAgent:
    """截图 → 当前页全部导航菜单（单次推理）。"""

    def __init__(self, config: MaiUiConfig | None = None) -> None:
        self.config = config or load_config()

    def predict_raw(self, image: Image.Image, *, retry_strict: bool = False) -> str:
        from mai_ui_agent.mlx_inference import predict_mlx_vision

        user_text = _RETRY_USER_INSTRUCTION if retry_strict else MENU_DETECT_USER_INSTRUCTION
        return predict_mlx_vision(
            MAI_MOBILE_SYS_PROMPT_MENU_DETECT,
            user_text,
            image,
            self.config,
            max_tokens_cap=_MENU_DETECT_MAX_TOKENS,
        )

    def _parse_raw(self, raw: str, w: int, h: int) -> MenuDetectResult:
        thinking, entries = parse_menu_detect_response(raw)
        menus: list[MenuItemResult] = []
        for entry in entries:
            if isinstance(entry, dict):
                menus.append(_menu_item_from_raw(entry, w, h))
        return MenuDetectResult(
            image_width=w,
            image_height=h,
            raw_text=raw,
            thinking=thinking,
            menus=menus,
            ok=True,
        )

    def detect(self, image: Image.Image | str | Path | bytes) -> MenuDetectResult:
        if isinstance(image, bytes):
            img = Image.open(BytesIO(image))
        elif isinstance(image, (str, Path)):
            img = load_image(image)
        else:
            img = image
        if img.mode != "RGB":
            img = img.convert("RGB")
        w, h = img.size

        raw = ""
        try:
            raw = self.predict_raw(img)
            try:
                return self._parse_raw(raw, w, h)
            except ValueError as parse_err:
                if self.config.verbose:
                    print("[mai_ui] 菜单 JSON 解析失败，使用严格格式重试…", flush=True)
                raw_retry = self.predict_raw(img, retry_strict=True)
                try:
                    return self._parse_raw(raw_retry, w, h)
                except ValueError as retry_err:
                    snippet = (raw_retry or raw)[:500]
                    raise ValueError(
                        f"{retry_err} 模型原始输出（节选）: {snippet!r}"
                    ) from retry_err
        except Exception as e:
            return MenuDetectResult(
                image_width=w,
                image_height=h,
                raw_text=raw,
                thinking=None,
                menus=[],
                ok=False,
                error=str(e),
            )
