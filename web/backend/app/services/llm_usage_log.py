"""统一记录大模型调用日志（含 token 用量，支持 API 返回或估算值）。"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("app.llm")


def estimate_tokens(text: str) -> int:
    """中英混合粗略估算 token 数。"""
    s = (text or "").strip()
    if not s:
        return 0
    total = 0.0
    for ch in s:
        total += 1.2 if ord(ch) > 127 else 0.25
    return max(0, int(round(total)))


def log_llm_usage(
    provider: str,
    operation: str,
    *,
    model: str | None = None,
    duration_ms: int | float | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    estimated: bool = False,
    run_id: int | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
        total_tokens = prompt_tokens + completion_tokens

    est_tag = " (估算)" if estimated else ""
    tok_part = ""
    if total_tokens is not None:
        tok_part = (
            f" tokens={total_tokens}{est_tag}"
            f" prompt={prompt_tokens if prompt_tokens is not None else '?'}"
            f" completion={completion_tokens if completion_tokens is not None else '?'}"
        )

    dur_part = f" {duration_ms}ms" if duration_ms is not None else ""
    model_part = f" model={model}" if model else ""
    run_part = f" run_id={run_id}" if run_id is not None else ""

    msg = f"[{provider}] {operation}{dur_part}{tok_part}{model_part}{run_part}"
    if extra:
        msg += f" extra={extra}"

    logger.info(msg)


def log_from_openai_usage(
    provider: str,
    operation: str,
    usage: Any,
    *,
    model: str | None = None,
    duration_ms: int | float | None = None,
    run_id: int | None = None,
) -> None:
    """从 OpenAI SDK response.usage 提取并记录。"""
    if usage is None:
        return
    pt = getattr(usage, "prompt_tokens", None)
    ct = getattr(usage, "completion_tokens", None)
    tt = getattr(usage, "total_tokens", None)
    if isinstance(usage, dict):
        pt = usage.get("prompt_tokens", pt)
        ct = usage.get("completion_tokens", ct)
        tt = usage.get("total_tokens", tt)
    log_llm_usage(
        provider,
        operation,
        model=model,
        duration_ms=duration_ms,
        prompt_tokens=int(pt) if pt is not None else None,
        completion_tokens=int(ct) if ct is not None else None,
        total_tokens=int(tt) if tt is not None else None,
        estimated=False,
        run_id=run_id,
    )


def log_midscene_machine_line(obj: dict[str, Any], *, run_id: int | None = None) -> None:
    """解析 Midscene 子进程 JSONL 中的 model_usage 事件。"""
    if obj.get("kind") != "model_usage":
        return
    log_llm_usage(
        "midscene",
        str(obj.get("label") or obj.get("op") or "call"),
        model=obj.get("model"),
        duration_ms=obj.get("duration_ms"),
        prompt_tokens=obj.get("prompt_tokens"),
        completion_tokens=obj.get("completion_tokens"),
        total_tokens=obj.get("total_tokens"),
        estimated=bool(obj.get("estimated")),
        run_id=run_id,
        extra={"op": obj.get("op")} if obj.get("op") else None,
    )
