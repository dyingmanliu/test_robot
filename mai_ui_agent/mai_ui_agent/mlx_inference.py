# SPDX-License-Identifier: Apache-2.0
"""In-process MAI-UI-2B inference via mlx_vlm (Qwen3-VL chat template)."""

from __future__ import annotations

import tempfile
import threading
from pathlib import Path

from PIL import Image

from mai_ui_agent.config import MaiUiConfig
from mai_ui_agent.image_utils import resize_for_grounding
from mai_ui_agent.prompt import MAI_MOBILE_SYS_PROMPT_GROUNDING

_MODEL = None
_PROCESSOR = None
_LOADED_PATH: str | None = None
_INFERENCE_LOCK = threading.Lock()

# Grounding 输出很短，限制生成长度以节省显存
_GROUNDING_MAX_TOKENS_CAP = 512


def resolve_mlx_model_path(config: MaiUiConfig) -> str:
    if config.model_path:
        p = Path(config.model_path).expanduser()
        if p.is_dir():
            return str(p.resolve())
        raise FileNotFoundError(f"MAI_UI_MODEL_PATH 不存在: {p}")

    name = (config.model_name or "").strip()
    if name:
        candidate = Path(name).expanduser()
        if candidate.is_dir():
            return str(candidate.resolve())

    local = config.pkg_root / "models" / "MAI-UI-2B-bf16-v2"
    if local.is_dir():
        return str(local.resolve())

    if name and not name.startswith("/"):
        return name

    raise FileNotFoundError(
        "未找到本地 MAI-UI 权重目录。请运行 scripts/download_model_hf.py，"
        "或在 .env 中设置 MAI_UI_MODEL_PATH=/path/to/MAI-UI-2B-bf16-v2"
    )


def _chat_processor(processor):
    if hasattr(processor, "apply_chat_template"):
        return processor
    if hasattr(processor, "tokenizer"):
        return processor.tokenizer
    raise TypeError("processor 不支持 apply_chat_template")


def build_vision_prompt(
    processor,
    system_prompt: str,
    user_text: str,
    image_path: str,
) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image_path},
                {"type": "text", "text": user_text},
            ],
        },
    ]
    proc = _chat_processor(processor)
    return proc.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )


def build_grounding_prompt(processor, instruction: str, image_path: str) -> str:
    return build_vision_prompt(
        processor,
        MAI_MOBILE_SYS_PROMPT_GROUNDING,
        instruction,
        image_path,
    )


def get_model_and_processor(model_path: str):
    global _MODEL, _PROCESSOR, _LOADED_PATH
    if _MODEL is not None and _LOADED_PATH == model_path:
        return _MODEL, _PROCESSOR

    from mlx_vlm import load

    _MODEL, _PROCESSOR = load(model_path)
    _LOADED_PATH = model_path
    return _MODEL, _PROCESSOR


def _run_generate(
    model,
    processor,
    system_prompt: str,
    user_text: str,
    image: Image.Image,
    config: MaiUiConfig,
    max_long_edge: int,
    max_tokens_cap: int,
) -> str:
    from mlx_vlm import generate

    infer_img, _orig = resize_for_grounding(image, max_long_edge=max_long_edge)
    max_tokens = min(config.max_tokens, max_tokens_cap)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        path = tmp.name
        infer_img.save(tmp, format="PNG")

    try:
        prompt = build_vision_prompt(processor, system_prompt, user_text, path)
        result = generate(
            model,
            processor,
            prompt=prompt,
            image=[path],
            max_tokens=max_tokens,
            temperature=config.temperature,
            verbose=config.verbose,
        )
        text = getattr(result, "text", result)
        return (text or "").strip()
    finally:
        Path(path).unlink(missing_ok=True)


def _predict_mlx_locked(
    system_prompt: str,
    user_text: str,
    image: Image.Image,
    config: MaiUiConfig,
    max_tokens_cap: int,
) -> str:
    model_path = resolve_mlx_model_path(config)
    model, processor = get_model_and_processor(model_path)

    edge = config.max_image_long_edge
    fallback_edge = min(960, edge) if edge > 960 else max(640, edge // 2)

    with _INFERENCE_LOCK:
        try:
            return _run_generate(
                model,
                processor,
                system_prompt,
                user_text,
                image,
                config,
                edge,
                max_tokens_cap,
            )
        except Exception as first_err:
            if fallback_edge >= edge:
                raise
            if config.verbose:
                print(
                    f"[mai_ui] 推理失败 ({first_err})，改用更小分辨率重试: "
                    f"long_edge={fallback_edge}",
                    flush=True,
                )
            return _run_generate(
                model,
                processor,
                system_prompt,
                user_text,
                image,
                config,
                fallback_edge,
                max_tokens_cap,
            )


def predict_mlx(instruction: str, image: Image.Image, config: MaiUiConfig) -> str:
    return _predict_mlx_locked(
        MAI_MOBILE_SYS_PROMPT_GROUNDING,
        instruction,
        image,
        config,
        _GROUNDING_MAX_TOKENS_CAP,
    )


def predict_mlx_vision(
    system_prompt: str,
    user_text: str,
    image: Image.Image,
    config: MaiUiConfig,
    max_tokens_cap: int = _GROUNDING_MAX_TOKENS_CAP,
) -> str:
    return _predict_mlx_locked(
        system_prompt,
        user_text,
        image,
        config,
        max_tokens_cap,
    )
