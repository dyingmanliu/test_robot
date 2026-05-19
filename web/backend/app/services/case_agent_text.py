"""将结构化用例字段拼接为 Agent 执行的自然语言任务（保留原有 task_text 作为补充说明）。"""

from __future__ import annotations

import json
import re
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


def _sanitize_midscene_instruction(text: str) -> str:
    """避免 Midscene 规划 XML/JSON 因嵌套双引号解析失败（见 midscene#2049）。"""
    s = (text or "").strip()
    if not s:
        return s
    for old, new in (
        ("\u201c", "「"),
        ("\u201d", "」"),
        ("\u2018", "「"),
        ("\u2019", "」"),
        ('"', "「"),
    ):
        s = s.replace(old, new)
    return s


def _split_compound_midscene_description(desc: str) -> list[str]:
    """将单步内多段 UI 操作拆成更短的 aiAct，降低规划失败率。"""
    d = desc.strip()
    if len(d) < 48:
        return [d]
    if ("弹窗" in d or "弹出" in d) and ("选择" in d or "确认" in d):
        if "选规格" in d or "加入购物车" in d:
            return [
                "点击菜单里第一款奶茶的选规格或加入购物车按钮",
                "在规格弹窗中保持默认口味与糖度，点击确认加入购物车",
            ]
    if "或" in d and d.count("，") >= 2:
        segs = [x.strip() for x in re.split(r"[，。；]", d) if x.strip()]
        if 2 <= len(segs) <= 4:
            return segs
    return [d]


def build_midscene_agent_steps(
    *,
    task_text: str,
    preconditions: str,
    steps_json: str,
    min_steps: int = 2,
) -> list[str] | None:
    """将结构化用例拆为 Midscene 逐步 aiAct 列表；步骤数不足时返回 None（走单段 agent_task）。"""
    steps = parse_steps_json(steps_json)
    lines: list[str] = []
    pre = _sanitize_midscene_instruction(preconditions)
    for i, s in enumerate(steps):
        if not isinstance(s, dict):
            continue
        desc = _sanitize_midscene_instruction(str(s.get("description", "")).strip())
        if not desc:
            continue
        exp = _sanitize_midscene_instruction(str(s.get("expected", "")).strip())
        sub_chunks = _split_compound_midscene_description(desc)
        for j, chunk in enumerate(sub_chunks):
            part = chunk
            if exp and j == len(sub_chunks) - 1:
                part += f"。预期：{exp}"
            if not lines and pre:
                part = f"【前置条件】{pre}\n{part}"
            lines.append(part)
    tt = (task_text or "").strip()
    if tt:
        if lines:
            lines.append(f"【执行说明】{tt}")
        else:
            lines.append(tt)
    if len(lines) < min_steps:
        return None
    return lines
