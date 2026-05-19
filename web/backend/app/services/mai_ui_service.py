"""MAI-UI 本地推理：健康检查与截图 Grounding（封装 mai_ui_agent）。"""

from __future__ import annotations

import base64
import logging
import sys
import time
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

from app.services.llm_usage_log import estimate_tokens, log_llm_usage

logger = logging.getLogger("app.llm")

_REPO_ROOT = Path(__file__).resolve().parents[4]
_MAI_UI_PKG_ROOT = _REPO_ROOT / "mai_ui_agent"
if str(_MAI_UI_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_MAI_UI_PKG_ROOT))


def _grounding_worker_status(
    url: str, timeout: float = 3.0
) -> tuple[bool, str, dict[str, Any]]:
    health_url = f"{url.rstrip('/')}/health"
    try:
        r = httpx.get(health_url, timeout=timeout)
        if r.status_code != 200:
            return False, f"Grounding 服务 HTTP {r.status_code}（{health_url}）", {}
        try:
            data = r.json()
        except Exception:
            data = {}
        if isinstance(data, dict) and data.get("ok"):
            return True, "Grounding 服务就绪（模型已加载）", data
        return True, "Grounding 服务可达", data if isinstance(data, dict) else {}
    except httpx.RequestError:
        return (
            False,
            f"Grounding 服务未启动（{health_url}）。"
            f"请在 mai_ui_agent 目录执行: bash scripts/serve_grounding_mlx.sh",
            {},
        )


def _grounding_worker_reachable(url: str, timeout: float = 3.0) -> bool:
    ok, _, _ = _grounding_worker_status(url, timeout=timeout)
    return ok


def _run_grounding_via_worker(
    image_bytes: bytes,
    instructions: list[str],
    grounding_url: str,
) -> dict[str, Any]:
    payload = {
        "image_base64": base64.b64encode(image_bytes).decode("ascii"),
        "instructions": instructions,
    }
    try:
        r = httpx.post(
            f"{grounding_url.rstrip('/')}/ground",
            json=payload,
            timeout=httpx.Timeout(600.0, connect=10.0),
        )
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        detail = ""
        if e.response is not None:
            try:
                body = e.response.json()
                if isinstance(body, dict) and body.get("error"):
                    detail = str(body["error"])
            except Exception:
                detail = e.response.text[:500]
        if not detail:
            detail = str(e)
        raise RuntimeError(
            f"Grounding 服务 HTTP {e.response.status_code}: {detail}"
        ) from e
    except httpx.RequestError as e:
        raise RuntimeError(
            f"无法连接 MAI-UI Grounding 服务 {grounding_url}。"
            f"请在 mai_ui_agent 目录执行: bash scripts/serve_grounding_mlx.sh"
        ) from e


def get_mai_ui_status() -> dict[str, Any]:
    from mai_ui_agent.config import load_config
    from mai_ui_agent.grounding import _mlx_vlm_available
    from mai_ui_agent.health import check_server, list_model_ids

    cfg = load_config()
    worker_ok, worker_message, worker_health = _grounding_worker_status(cfg.grounding_url)

    ok, openai_message = check_server(cfg)
    available: list[str] = []
    if ok:
        try:
            available = list_model_ids(cfg)
        except Exception:
            pass
    model_ok = cfg.model_name in available if available else None

    use_mlx = cfg.backend == "mlx_vlm"
    if use_mlx:
        reachable = worker_ok
        message = worker_message
    else:
        reachable = worker_ok or ok
        if worker_ok:
            message = worker_message
        elif ok:
            message = openai_message
        else:
            message = (
                f"{worker_message}\n"
                f"OpenAI 兼容服务: {openai_message}"
            )

    model_loaded = bool(worker_health.get("ok")) if worker_ok else False
    worker_model_path = worker_health.get("model_path") if worker_ok else None

    return {
        "reachable": reachable,
        "message": message,
        "backend": cfg.backend,
        "grounding_url": cfg.grounding_url,
        "grounding_worker_ready": worker_ok,
        "model_loaded": model_loaded,
        "worker_model_path": worker_model_path,
        "base_url": cfg.base_url,
        "openai_api_reachable": ok,
        "model_name": cfg.model_name,
        "model_path": cfg.model_path or worker_model_path,
        "model_name_registered": model_ok if not use_mlx else None,
        "available_models": available if not use_mlx else [],
        "max_tokens": cfg.max_tokens,
        "temperature": cfg.temperature,
        "mlx_vlm_in_process": _mlx_vlm_available(),
    }


def run_grounding(image_bytes: bytes, instructions: list[str]) -> dict[str, Any]:
    from mai_ui_agent.config import load_config
    from mai_ui_agent.grounding import MaiUiGroundingAgent, _mlx_vlm_available

    if not instructions:
        raise ValueError("请至少提供一条定位描述")

    cfg = load_config()
    t0 = time.perf_counter()
    if _grounding_worker_reachable(cfg.grounding_url):
        out = _run_grounding_via_worker(image_bytes, instructions, cfg.grounding_url)
        duration_ms = int((time.perf_counter() - t0) * 1000)
        log_llm_usage(
            "mai_ui",
            f"grounding/worker x{len(instructions)}",
            model=cfg.model_name,
            duration_ms=duration_ms,
            estimated=True,
            extra={"via": "grounding_server"},
        )
        return out

    if cfg.backend == "mlx_vlm" and not _mlx_vlm_available():
        raise RuntimeError(
            f"MAI-UI 需要 mlx_vlm Grounding 服务（{cfg.grounding_url}）。"
            "在 mai_ui_agent 目录执行: bash scripts/serve_grounding_mlx.sh"
        )

    img = Image.open(BytesIO(image_bytes))
    if img.mode != "RGB":
        img = img.convert("RGB")

    agent = MaiUiGroundingAgent(cfg)
    results = []
    for q in instructions:
        if not q.strip():
            continue
        q0 = time.perf_counter()
        results.append(agent.ground(q.strip(), img).to_dict())
        duration_ms = int((time.perf_counter() - q0) * 1000)
        log_llm_usage(
            "mai_ui",
            "grounding/in_process",
            model=cfg.model_name,
            duration_ms=duration_ms,
            prompt_tokens=estimate_tokens(q),
            estimated=True,
        )
    return {
        "image_width": img.size[0],
        "image_height": img.size[1],
        "results": results,
    }


def _run_menu_detect_via_worker(image_bytes: bytes, grounding_url: str) -> dict[str, Any]:
    payload = {"image_base64": base64.b64encode(image_bytes).decode("ascii")}
    try:
        r = httpx.post(
            f"{grounding_url.rstrip('/')}/detect-menus",
            json=payload,
            timeout=httpx.Timeout(600.0, connect=10.0),
        )
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        detail = ""
        if e.response is not None:
            try:
                body = e.response.json()
                if isinstance(body, dict) and body.get("error"):
                    detail = str(body["error"])
            except Exception:
                detail = e.response.text[:500]
        if not detail:
            detail = str(e)
        raise RuntimeError(
            f"菜单识别服务 HTTP {e.response.status_code}: {detail}"
        ) from e
    except httpx.RequestError as e:
        raise RuntimeError(
            f"无法连接 MAI-UI Grounding 服务 {grounding_url}。"
            "在 mai_ui_agent 目录执行: bash scripts/serve_grounding_mlx.sh"
        ) from e


def run_menu_detect(image_bytes: bytes) -> dict[str, Any]:
    from mai_ui_agent.config import load_config
    from mai_ui_agent.grounding import _mlx_vlm_available
    from mai_ui_agent.menu_detect import MaiUiMenuDetectAgent

    cfg = load_config()
    t0 = time.perf_counter()
    if _grounding_worker_reachable(cfg.grounding_url):
        try:
            out = _run_menu_detect_via_worker(image_bytes, cfg.grounding_url)
            duration_ms = int((time.perf_counter() - t0) * 1000)
            n = len(out.get("menus") or [])
            log_llm_usage(
                "mai_ui",
                "detect-menus/worker",
                model=cfg.model_name,
                duration_ms=duration_ms,
                estimated=True,
                extra={"menus": n},
            )
            return out
        except RuntimeError as e:
            err = str(e)
            if "404" not in err and "not found" not in err.lower():
                raise
            if cfg.verbose:
                print(
                    "[mai_ui] Grounding 服务无 /detect-menus，"
                    "请重启 serve_grounding_mlx.sh；尝试进程内推理…",
                    flush=True,
                )

    if cfg.backend == "mlx_vlm" and not _mlx_vlm_available():
        raise RuntimeError(
            f"MAI-UI 需要 mlx_vlm Grounding 服务（{cfg.grounding_url}）。"
            "在 mai_ui_agent 目录执行: bash scripts/serve_grounding_mlx.sh"
        )

    agent = MaiUiMenuDetectAgent(cfg)
    out = agent.detect(image_bytes).to_dict()
    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_llm_usage(
        "mai_ui",
        "detect-menus/in_process",
        model=cfg.model_name,
        duration_ms=duration_ms,
        estimated=True,
        extra={"menus": len(out.get("menus") or [])},
    )
    return out
