"""从仓库根目录 `.env` 或 `mai_ui_agent/.env` 加载 MAI-UI 推理服务配置。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_PKG_ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT = _PKG_ROOT.parent


def _load_dotenv() -> None:
    root_env = _REPO_ROOT / ".env"
    local_env = _PKG_ROOT / ".env"
    if root_env.is_file():
        load_dotenv(root_env)
    elif local_env.is_file():
        load_dotenv(local_env)
    else:
        load_dotenv()


def _default_local_model_dir() -> Path:
    return _PKG_ROOT / "models" / "MAI-UI-2B-bf16-v2"


def _infer_backend(base_url: str, explicit: str | None) -> str:
    if explicit and explicit.strip().lower() not in ("", "auto"):
        return explicit.strip().lower()
    if _default_local_model_dir().is_dir():
        return "mlx_vlm"
    if ":8100" in base_url:
        return "openai"
    return "openai"


@dataclass
class MaiUiConfig:
    """MAI-UI-2B Grounding：OpenAI 兼容 API 或本地 mlx_vlm。"""

    base_url: str
    api_key: str
    model_name: str
    backend: str = "auto"
    model_path: str | None = None
    grounding_url: str = "http://127.0.0.1:8101"
    temperature: float = 0.0
    top_p: float = 1.0
    top_k: int = -1
    max_tokens: int = 2048
    max_retries: int = 3
    max_image_long_edge: int = 1280
    verbose: bool = False
    pkg_root: Path = _PKG_ROOT

    @property
    def runtime_conf(self) -> dict:
        return {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "max_tokens": self.max_tokens,
        }


def load_config(overrides: dict | None = None) -> MaiUiConfig:
    _load_dotenv()
    o = overrides or {}

    def _truthy(name: str, default: bool = False) -> bool:
        raw = os.getenv(name)
        if raw is None:
            return default
        return raw.strip().lower() in ("1", "true", "yes", "on")

    base_url = o.get("base_url") or os.getenv("MAI_UI_BASE_URL", "http://127.0.0.1:8100/v1")
    default_model = "MAI-UI-2B" if ":8100" in base_url else "maternion/mai-ui:2b"
    model_name = o.get("model_name") or os.getenv("MAI_UI_MODEL") or default_model
    default_key = "empty" if ":8100" in base_url else "ollama"

    model_path = o.get("model_path") or os.getenv("MAI_UI_MODEL_PATH")
    if not model_path:
        local = _default_local_model_dir()
        if local.is_dir():
            model_path = str(local)

    backend_raw = o.get("backend") or os.getenv("MAI_UI_BACKEND")
    backend = _infer_backend(base_url, backend_raw)

    grounding_url = (
        o.get("grounding_url")
        or os.getenv("MAI_UI_GROUNDING_URL")
        or "http://127.0.0.1:8101"
    )

    return MaiUiConfig(
        base_url=base_url,
        api_key=o.get("api_key") or os.getenv("MAI_UI_API_KEY", default_key),
        model_name=model_name,
        backend=backend,
        model_path=model_path,
        grounding_url=grounding_url.rstrip("/"),
        temperature=float(o.get("temperature", os.getenv("MAI_UI_TEMPERATURE", "0"))),
        top_p=float(o.get("top_p", os.getenv("MAI_UI_TOP_P", "1"))),
        top_k=int(o.get("top_k", os.getenv("MAI_UI_TOP_K", "-1"))),
        max_tokens=int(o.get("max_tokens", os.getenv("MAI_UI_MAX_TOKENS", "2048"))),
        max_retries=int(o.get("max_retries", os.getenv("MAI_UI_MAX_RETRIES", "3"))),
        max_image_long_edge=int(
            o.get("max_image_long_edge", os.getenv("MAI_UI_MAX_IMAGE_LONG_EDGE", "1280"))
        ),
        verbose=_truthy("MAI_UI_VERBOSE", False),
    )
