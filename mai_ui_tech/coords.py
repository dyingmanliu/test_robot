"""坐标换算：MAI-UI 使用 0–999 尺度，与 AutoGLM 1000 尺度及像素坐标互转。"""

from __future__ import annotations

SCALE_FACTOR = 999


def norm_to_pixel(x_norm: float, y_norm: float, width: int, height: int) -> tuple[int, int]:
    """归一化 [0,1] → 像素。"""
    return int(round(x_norm * width)), int(round(y_norm * height))


def norm999_to_norm1000(x999: int, y999: int) -> tuple[int, int]:
    """0–999 → 0–1000（与 autoglm element 尺度对齐）。"""
    return int(round(x999 / SCALE_FACTOR * 1000)), int(round(y999 / SCALE_FACTOR * 1000))


def norm_to_norm999(x_norm: float, y_norm: float) -> tuple[int, int]:
    return int(round(x_norm * SCALE_FACTOR)), int(round(y_norm * SCALE_FACTOR))
