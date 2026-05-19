"""structured 与 Midscene YAML 用例格式互转。"""

from __future__ import annotations

from typing import Any

from app.schemas import CaseStepJson
from app.services.case_yaml import validate_case_yaml


def structured_to_yaml(
    *,
    title: str,
    preconditions: str,
    steps: list[CaseStepJson] | list[dict[str, Any]],
    task_text: str,
) -> str:
    """将结构化字段转为 Midscene YAML（单 task，flow 为 ai / aiAssert）。"""
    try:
        import yaml as pyyaml
    except ImportError as e:
        raise RuntimeError("请安装 PyYAML：pip install pyyaml") from e

    flow: list[dict[str, Any]] = []
    pre = (preconditions or "").strip()
    if pre:
        flow.append({"ai": f"确保满足前置条件：{pre}"})

    order = 0
    for raw in steps:
        if isinstance(raw, CaseStepJson):
            desc = (raw.description or "").strip()
            exp = (raw.expected or "").strip()
        elif isinstance(raw, dict):
            desc = str(raw.get("description", "")).strip()
            exp = str(raw.get("expected", "")).strip()
        else:
            continue
        if not desc and not exp:
            continue
        order += 1
        if desc:
            flow.append({"ai": desc})
        if exp:
            flow.append({"aiAssert": exp})

    tt = (task_text or "").strip()
    if tt:
        flow.append({"ai": f"【执行说明】{tt}"})

    if not flow:
        flow.append({"ai": (title or "执行测试").strip() or "执行测试"})

    task_name = (title or "测试任务").strip() or "测试任务"
    doc = {"tasks": [{"name": task_name, "flow": flow}]}
    text = pyyaml.dump(
        doc,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    return validate_case_yaml(text)


def yaml_to_structured(case_yaml: str) -> dict[str, Any]:
    """将 Midscene YAML 解析为结构化字段（最佳努力，与 structured_to_yaml 约定对应）。"""
    text = validate_case_yaml(case_yaml)
    import yaml as pyyaml

    doc = pyyaml.safe_load(text)
    title = "未命名用例"
    preconditions = ""
    task_text_parts: list[str] = []
    steps: list[CaseStepJson] = []

    tasks = doc.get("tasks") if isinstance(doc, dict) else None
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("YAML 中无有效 tasks")

    first = tasks[0] if isinstance(tasks[0], dict) else {}
    title = str(first.get("name") or title).strip() or title
    flow = first.get("flow")
    if not isinstance(flow, list):
        raise ValueError("YAML 首个 task 缺少 flow 列表")

    pending_desc: str | None = None
    order = 0

    def flush_step(desc: str, exp: str) -> None:
        nonlocal order
        if not desc and not exp:
            return
        order += 1
        steps.append(
            CaseStepJson(order=order, description=desc, expected=exp)
        )

    for item in flow:
        if isinstance(item, str):
            if pending_desc:
                flush_step(pending_desc, "")
            pending_desc = item.strip()
            continue
        if not isinstance(item, dict):
            continue
        if "ai" in item:
            ai_text = str(item["ai"]).strip()
            if ai_text.startswith("确保满足前置条件："):
                preconditions = ai_text[len("确保满足前置条件：") :].strip()
                continue
            if ai_text.startswith("【执行说明】"):
                task_text_parts.append(ai_text[len("【执行说明】") :].strip())
                continue
            if pending_desc:
                flush_step(pending_desc, "")
            pending_desc = ai_text
        elif "aiAssert" in item:
            exp = str(item["aiAssert"]).strip()
            if pending_desc:
                flush_step(pending_desc, exp)
                pending_desc = None
            elif steps:
                steps[-1].expected = exp
            else:
                flush_step("", exp)

    if pending_desc:
        flush_step(pending_desc, "")

    return {
        "title": title,
        "preconditions": preconditions,
        "steps": steps,
        "task_text": "\n".join(p for p in task_text_parts if p),
    }
