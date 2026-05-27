"""解析机器人实例的知识库绑定与 Skill 配置。"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.knowledge.config import DEFAULT_RAG_POLICY, rag_default_mode
from app.knowledge.query.service import merge_rag_policy
from app.models import Project, ProjectKnowledgeSettings, RobotInstance, RobotInstanceBinding, SkillProfile
from app.services.robot_catalog import is_analysis_catalog


def _parse_json_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _parse_json_dict(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def default_skill_profile_for_catalog(db: Session, catalog_robot_id: str) -> SkillProfile | None:
    return (
        db.query(SkillProfile)
        .filter(SkillProfile.catalog_robot_id == catalog_robot_id, SkillProfile.is_default.is_(True))
        .first()
    )


def resolve_robot_agent_context(
    db: Session,
    *,
    robot_instance_id: int,
    project_id: int | None = None,
    owner_scope_ids: list[int] | None = None,
) -> dict[str, Any]:
    inst = db.query(RobotInstance).filter(RobotInstance.id == robot_instance_id).first()
    if inst is None:
        raise ValueError("机器人实例不存在")

    binding = (
        db.query(RobotInstanceBinding)
        .filter(RobotInstanceBinding.robot_instance_id == robot_instance_id)
        .first()
    )
    collection_ids: list[int] = []
    skill_names: list[str] = []
    profile: SkillProfile | None = None
    if binding:
        collection_ids = [int(x) for x in _parse_json_list(binding.knowledge_collection_ids_json) if str(x).isdigit()]
        if binding.skill_profile_id:
            profile = db.query(SkillProfile).filter(SkillProfile.id == binding.skill_profile_id).first()
    if profile is None:
        profile = default_skill_profile_for_catalog(db, inst.catalog_robot_id)
    if profile:
        skill_names = [str(x) for x in _parse_json_list(profile.skill_names_json)]

    project_policy: dict = {}
    if project_id is not None:
        ps = db.query(ProjectKnowledgeSettings).filter(ProjectKnowledgeSettings.project_id == project_id).first()
        if ps:
            project_policy = _parse_json_dict(ps.rag_policy_json)

    override = _parse_json_dict(binding.rag_policy_override_json if binding else None)
    rag_policy = merge_rag_policy(project_policy, override)

    return {
        "robot_instance_id": robot_instance_id,
        "catalog_robot_id": inst.catalog_robot_id,
        "is_analysis": is_analysis_catalog(inst.catalog_robot_id),
        "knowledge_collection_ids": collection_ids,
        "skill_names": skill_names,
        "skill_profile_id": profile.id if profile else None,
        "rag_policy": rag_policy,
        "rag_mode": rag_default_mode(),
        "project_id": project_id,
        "owner_scope_ids": owner_scope_ids,
    }
