# SPDX-License-Identifier: Apache-2.0
"""Grounding 前缩小截图，降低 Mac 16GB 上 MLX Metal 显存/页错误风险。"""

from __future__ import annotations

from PIL import Image


def resize_for_grounding(
    image: Image.Image,
    max_long_edge: int = 1280,
) -> tuple[Image.Image, tuple[int, int]]:
    """等比缩小，使长边不超过 max_long_edge。返回 (推理用图, 原始宽高)。"""
    if max_long_edge <= 0:
        w, h = image.size
        return image, (w, h)

    w, h = image.size
    long_edge = max(w, h)
    if long_edge <= max_long_edge:
        return image, (w, h)

    scale = max_long_edge / long_edge
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    resized = image.resize((nw, nh), Image.Resampling.LANCZOS)
    return resized, (w, h)
