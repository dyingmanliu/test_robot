"""LLM JSON 输出解析与 structured 用例校验。"""

from __future__ import annotations

import json
import re
from typing import Any

from analysis_agent.errors import AnalysisAgentError
from analysis_agent.types import CaseDraft, CaseStep

_VALID_PRIORITIES = frozenset({"P0", "P1", "P2", "P3"})


def extract_json_object(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        raise AnalysisAgentError("模型返回为空")
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw, re.IGNORECASE)
    if fence:
        raw = fence.group(1).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(raw[start : end + 1])
            except json.JSONDecodeError as e:
                raise AnalysisAgentError(f"无法解析模型 JSON：{e}") from e
        else:
            raise AnalysisAgentError("模型未返回有效 JSON") from None
    if not isinstance(data, dict):
        raise AnalysisAgentError("模型 JSON 根节点须为对象")
    return data


def normalize_steps(raw_steps: Any) -> list[CaseStep]:
    if not isinstance(raw_steps, list):
        return []
    out: list[CaseStep] = []
    for i, item in enumerate(raw_steps, start=1):
        if not isinstance(item, dict):
            continue
        desc = str(item.get("description", "")).strip()
        exp = str(item.get("expected", "")).strip()
        if not desc and not exp:
            continue
        order_raw = item.get("order")
        try:
            order = int(order_raw) if order_raw is not None else i
        except (TypeError, ValueError):
            order = i
        out.append(CaseStep(order=max(1, order), description=desc, expected=exp))
    for idx, step in enumerate(out, start=1):
        step.order = idx
    return out


def validate_structured_draft(
    *,
    title: str,
    task_text: str,
    steps: list[CaseStep],
) -> None:
    if not title.strip():
        raise AnalysisAgentError("生成结果缺少标题")
    if not task_text.strip() and not steps:
        raise AnalysisAgentError("请填写「执行说明」或至少一条「测试步骤」")


def draft_from_parsed(data: dict[str, Any]) -> CaseDraft:
    title = str(data.get("title", "")).strip()
    if len(title) > 256:
        title = title[:256]

    priority = str(data.get("priority", "P2")).strip().upper()
    if priority not in _VALID_PRIORITIES:
        priority = "P2"

    preconditions = str(data.get("preconditions", "")).strip()
    task_text = str(data.get("task_text", "")).strip()
    steps = normalize_steps(data.get("steps"))

    validate_structured_draft(title=title, task_text=task_text, steps=steps)

    return CaseDraft(
        title=title,
        preconditions=preconditions,
        steps=steps,
        task_text=task_text,
        priority=priority,
    )
