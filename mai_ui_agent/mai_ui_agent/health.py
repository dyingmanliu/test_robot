"""检查本地 MAI-UI 推理服务是否可用。"""

from __future__ import annotations

import httpx

from mai_ui_agent.config import MaiUiConfig, load_config


def _models_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return f"{base}/models"
    return f"{base}/v1/models"


def list_model_ids(config: MaiUiConfig | None = None, timeout: float = 5.0) -> list[str]:
    cfg = config or load_config()
    url = _models_url(cfg.base_url)
    headers = {}
    if cfg.api_key and cfg.api_key not in ("empty", "ollama"):
        headers["Authorization"] = f"Bearer {cfg.api_key}"
    r = httpx.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    items = data.get("data") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    ids: list[str] = []
    for item in items:
        if isinstance(item, dict) and item.get("id"):
            ids.append(str(item["id"]))
    return ids


def check_server(config: MaiUiConfig | None = None, timeout: float = 5.0) -> tuple[bool, str]:
    cfg = config or load_config()
    url = _models_url(cfg.base_url)

    headers = {}
    if cfg.api_key and cfg.api_key not in ("empty", "ollama"):
        headers["Authorization"] = f"Bearer {cfg.api_key}"

    try:
        r = httpx.get(url, headers=headers, timeout=timeout)
        if r.status_code != 200:
            return False, f"HTTP {r.status_code} from {url}: {r.text[:200]}"

        ids = list_model_ids(cfg, timeout=timeout)
        lines = [f"OK {url}", f"配置模型: {cfg.model_name}"]
        if ids:
            lines.append(f"服务端可用模型: {', '.join(ids)}")
            if cfg.model_name not in ids:
                lines.append(
                    f"警告: MAI_UI_MODEL={cfg.model_name!r} 不在列表中，"
                    f"请改为 {ids[0]!r} 或启动时 --served-model-name"
                )
        return True, "\n".join(lines)
    except Exception as e:
        return False, f"无法连接 {url}: {e}"
