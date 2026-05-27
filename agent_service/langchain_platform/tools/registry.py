"""Skill 注册表：catalog_robot_id → LangChain Tool 名称。"""
from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from agent_service.langchain_platform.tools.device_autoglm import list_connected_devices_hint

SKILLS_BY_CATALOG: dict[str, list[str]] = {
    "test_analysis": ["search_case_kb", "validate_case_draft"],
    "test_execution": ["preflight_device"],
}

_TOOL_INSTANCES: dict[str, BaseTool] = {
    "preflight_device": list_connected_devices_hint,
}


def list_skills(catalog_robot_id: str) -> list[str]:
    return list(SKILLS_BY_CATALOG.get(catalog_robot_id, []))


def get_tools(catalog_robot_id: str) -> list[BaseTool]:
    names = list_skills(catalog_robot_id)
    return [_TOOL_INSTANCES[n] for n in names if n in _TOOL_INSTANCES]


def register_skill(catalog_robot_id: str, skill_name: str, tool: BaseTool | None = None) -> None:
    skills = SKILLS_BY_CATALOG.setdefault(catalog_robot_id, [])
    if skill_name not in skills:
        skills.append(skill_name)
    if tool is not None:
        _TOOL_INSTANCES[skill_name] = tool
