"""Skill 注册表：catalog_robot_id → LangChain Tool 名称。"""
from __future__ import annotations

from langchain_core.tools import BaseTool

from agent_service.langchain_platform.tools.device_autoglm import list_connected_devices_hint

SKILLS_BY_CATALOG: dict[str, list[str]] = {
    "test_analysis": ["query_knowledge", "validate_case_draft", "query_feature_context"],
    "functional_execution": [
        "query_knowledge",
        "search_ui_element",
        "search_execution_hint",
        "preflight_device",
    ],
    "specialized_execution": ["query_knowledge", "search_execution_hint", "preflight_device"],
}

_TOOL_INSTANCES: dict[str, BaseTool] = {
    "preflight_device": list_connected_devices_hint,
}


def list_skills(catalog_robot_id: str) -> list[str]:
    return list(SKILLS_BY_CATALOG.get(catalog_robot_id, []))


def get_tools(catalog_robot_id: str, skill_names: list[str] | None = None) -> list[BaseTool]:
    names = skill_names if skill_names is not None else list_skills(catalog_robot_id)
    return [_TOOL_INSTANCES[n] for n in names if n in _TOOL_INSTANCES]


def register_skill(catalog_robot_id: str, skill_name: str, tool: BaseTool | None = None) -> None:
    skills = SKILLS_BY_CATALOG.setdefault(catalog_robot_id, [])
    if skill_name not in skills:
        skills.append(skill_name)
    if tool is not None:
        _TOOL_INSTANCES[skill_name] = tool
