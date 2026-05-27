"""启动时初始化 Skill Profile 等知识库种子数据。"""
from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from app.models import SkillProfile

log = logging.getLogger(__name__)

_DEFAULT_PROFILES = [
    {
        "catalog_robot_id": "test_analysis",
        "name": "测试分析默认",
        "skills": ["query_knowledge", "validate_case_draft", "query_feature_context"],
    },
    {
        "catalog_robot_id": "functional_execution",
        "name": "功能执行默认",
        "skills": ["query_knowledge", "search_ui_element", "search_execution_hint", "preflight_device"],
    },
    {
        "catalog_robot_id": "specialized_execution",
        "name": "专项执行默认",
        "skills": ["query_knowledge", "search_execution_hint", "preflight_device"],
    },
]


def ensure_skill_profiles(db: Session) -> None:
    for spec in _DEFAULT_PROFILES:
        exists = (
            db.query(SkillProfile)
            .filter(
                SkillProfile.catalog_robot_id == spec["catalog_robot_id"],
                SkillProfile.is_default.is_(True),
            )
            .first()
        )
        if exists:
            continue
        db.add(
            SkillProfile(
                catalog_robot_id=spec["catalog_robot_id"],
                name=spec["name"],
                skill_names_json=json.dumps(spec["skills"], ensure_ascii=False),
                is_default=True,
            )
        )
    db.commit()
