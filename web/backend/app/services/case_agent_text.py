"""将结构化用例字段拼接为 Agent 执行的自然语言任务（保留原有 task_text 作为补充说明）。"""

from __future__ import annotations

import json
from typing import Any


def parse_steps_json(raw: str | None) -> list[dict[str, Any]]:
    if not raw or not str(raw).strip():
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        return []
    except json.JSONDecodeError:
        return []


def build_agent_task_text(
    *,
    task_text: str,
    preconditions: str,
    steps_json: str,
) -> str:
    """供 PhoneTestAgent 执行的单段任务文本。"""
    blocks: list[str] = []
    pre = (preconditions or "").strip()
    if pre:
        blocks.append("【前置条件】\n" + pre)

    steps = parse_steps_json(steps_json)
    if steps:
        lines: list[str] = []
        for i, s in enumerate(steps, start=1):
            if not isinstance(s, dict):
                continue
            order = s.get("order")
            if order is None:
                order = i
            desc = str(s.get("description", "")).strip()
            exp = str(s.get("expected", "")).strip()
            line = f"{order}. {desc}" if desc else f"{order}."
            if exp:
                line += f"\n   预期：{exp}"
            lines.append(line)
        if lines:
            blocks.append("【测试步骤】\n" + "\n".join(lines))

    tt = (task_text or "").strip()
    if tt:
        blocks.append("【执行说明】\n" + tt)

    if not blocks:
        return tt or "（空用例）"
    return "\n\n".join(blocks)
