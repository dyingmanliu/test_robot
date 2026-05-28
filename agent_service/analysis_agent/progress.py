"""用例生成过程日志回调（SSE / Web job step_log）。"""
from __future__ import annotations

import time
from typing import Any, Callable

CaseGenProgressFn = Callable[[dict[str, Any]], None]

_LOG_PREVIEW_MAX = 1200


def truncate_log_text(text: str, max_len: int = _LOG_PREVIEW_MAX) -> str:
    t = (text or "").strip()
    if len(t) <= max_len:
        return t
    return t[:max_len] + "…"


def emit_case_gen_progress(
    cb: CaseGenProgressFn | None,
    *,
    phase: str,
    message: str,
    **extra: Any,
) -> None:
    if cb is None:
        return
    cb(
        {
            "kind": "case_gen_log",
            "phase": phase,
            "message": message,
            **extra,
        }
    )


def _message_chars(messages: list[Any]) -> tuple[int, int, str]:
    """返回 (system_chars, user_chars, 人类可读摘要)。"""
    sys_chars = 0
    user_chars = 0
    labels: list[str] = []
    for m in messages:
        content = str(getattr(m, "content", "") or "")
        name = type(m).__name__
        if "System" in name:
            sys_chars += len(content)
            labels.append(f"system {len(content)}字")
        elif "Human" in name or "User" in name:
            user_chars += len(content)
            labels.append(f"user {len(content)}字")
        elif "AI" in name or "Assistant" in name:
            labels.append(f"assistant {len(content)}字")
        else:
            labels.append(f"{name} {len(content)}字")
    return sys_chars, user_chars, "，".join(labels)


def _token_usage_from_response(resp: Any) -> dict[str, Any]:
    meta = getattr(resp, "response_metadata", None) or {}
    usage = dict(meta.get("token_usage") or meta.get("usage") or {})
    um = getattr(resp, "usage_metadata", None)
    if um is not None:
        for src_key, dst_key in (
            ("input_tokens", "prompt_tokens"),
            ("output_tokens", "completion_tokens"),
            ("total_tokens", "total_tokens"),
        ):
            val = getattr(um, src_key, None)
            if val is not None and dst_key not in usage:
                usage[dst_key] = val
    return {k: int(v) for k, v in usage.items() if v is not None}


def emit_llm_request(
    cb: CaseGenProgressFn | None,
    *,
    model: str,
    messages: list[Any],
    attempt: int = 1,
    extra_note: str = "",
) -> None:
    sys_chars, user_chars, summary = _message_chars(messages)
    human_preview = ""
    for m in reversed(messages):
        name = type(m).__name__
        if "Human" in name or "User" in name:
            human_preview = truncate_log_text(str(getattr(m, "content", "") or ""), 600)
            break
    note = f"（第 {attempt} 次）" if attempt > 1 else ""
    extra = f" {extra_note}" if extra_note else ""
    emit_case_gen_progress(
        cb,
        phase="llm_request",
        message=f"请求模型 {model}{note}：{summary}{extra}",
        model=model,
        attempt=attempt,
        system_chars=sys_chars,
        user_chars=user_chars,
        request_preview=human_preview,
    )


def emit_llm_response(
    cb: CaseGenProgressFn | None,
    *,
    model: str,
    resp: Any,
    elapsed_ms: float,
    attempt: int = 1,
) -> None:
    raw = str(getattr(resp, "content", "") or "").strip()
    usage = _token_usage_from_response(resp)
    parts = [f"{len(raw)} 字", f"{elapsed_ms:.0f}ms"]
    if usage.get("total_tokens") is not None:
        parts.append(f"tokens {usage['total_tokens']}")
    elif usage.get("prompt_tokens") is not None or usage.get("completion_tokens") is not None:
        pt = usage.get("prompt_tokens", "?")
        ct = usage.get("completion_tokens", "?")
        parts.append(f"tokens {pt}+{ct}")
    note = f"（第 {attempt} 次）" if attempt > 1 else ""
    emit_case_gen_progress(
        cb,
        phase="llm_response",
        message=f"模型返回{note}：" + "，".join(parts),
        model=model,
        attempt=attempt,
        output_preview=truncate_log_text(raw),
        token_usage=usage or None,
        elapsed_ms=round(elapsed_ms),
        output_chars=len(raw),
    )


def invoke_chat_with_progress(
    llm: Any,
    messages: list[Any],
    *,
    on_progress: CaseGenProgressFn | None,
    model_name: str,
    attempt: int = 1,
) -> Any:
    """调用 Chat 模型并推送请求/响应日志。"""
    emit_llm_request(on_progress, model=model_name, messages=messages, attempt=attempt)
    t0 = time.perf_counter()
    try:
        resp = llm.invoke(messages)
    except Exception as exc:
        emit_case_gen_progress(
            on_progress,
            phase="llm_error",
            message=f"模型调用失败：{exc}",
            model=model_name,
            attempt=attempt,
        )
        raise
    emit_llm_response(
        on_progress,
        model=model_name,
        resp=resp,
        elapsed_ms=(time.perf_counter() - t0) * 1000,
        attempt=attempt,
    )
    return resp


def emit_kb_http_log(
    cb: CaseGenProgressFn | None,
    *,
    query: str,
    doc_types: list[str] | None,
    data: dict[str, Any],
    call_index: int,
) -> None:
    items = data.get("items") or []
    err = data.get("error")
    lat = data.get("latency_ms")
    lat_s = f"，耗时 {lat}ms" if lat is not None else ""
    if err:
        emit_case_gen_progress(
            cb,
            phase="kb_http",
            message=f"知识库 HTTP 失败：{err}",
            query=truncate_log_text(query, 200),
            doc_types=",".join(doc_types or []),
            call_index=call_index,
        )
        return
    titles = "；".join(
        f"{it.get('doc_type', '')}:{(it.get('title') or '')[:24]}"
        for it in items[:4]
    )
    emit_case_gen_progress(
        cb,
        phase="kb_http",
        message=f"POST /api/internal/knowledge/query 第 {call_index} 次，命中 {len(items)} 条{lat_s}",
        query=truncate_log_text(query, 200),
        doc_types=",".join(doc_types or []),
        hits=len(items),
        latency_ms=lat,
        call_index=call_index,
        detail_preview=titles or None,
    )
