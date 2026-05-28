"""Web 适配层：组装 ORM / KB 上下文，通过 HTTP 调用 analysis_agent 服务。"""

from __future__ import annotations

import logging

log = logging.getLogger("app.case_generation")
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Project, RobotInstance, User
from app.rbac import can_view_all_cases
from app.schemas import CaseStepJson
from app.services.analysis_instance_guard import instance_available_for_generation
from app.services.case_kb import search_cases_kb
from app.services.company_scope import (
    can_use_robot_instance,
    company_shares_projects_cases,
    enterprise_colleague_user_ids,
)

class AnalysisAgentError(Exception):
    """用户可见的错误。"""


# 兼容旧引用
CaseGeneratorError = AnalysisAgentError


def _kb_owner_scope(db: Session, user: User) -> Optional[list[int]]:
    if can_view_all_cases(user):
        return None
    if company_shares_projects_cases(db, user):
        return enterprise_colleague_user_ids(db, user)
    return [user.id]


def _fetch_kb_examples(
    db: Session,
    *,
    project: Project,
    user: User,
    prompt: str,
    limit: int = 3,
) -> tuple[list[str], list[int]]:
    scope = _kb_owner_scope(db, user)
    rows = search_cases_kb(
        db,
        q=prompt[:200],
        project_id=project.id,
        owner_scope_ids=scope,
        limit=limit,
    )
    snippets: list[str] = []
    case_ids: list[int] = []
    for tc, kb in rows:
        case_ids.append(tc.id)
        blob = (kb.search_text if kb else "") or ""
        if not blob.strip():
            continue
        snippets.append(f"【参考用例 {tc.title}】\n{blob[:600]}")
    return snippets, case_ids


def _project_context(project: Project) -> dict[str, str]:
    return {
        "name": project.name,
        "tested_app_name": project.tested_app_name or "",
        "test_objective": (project.test_objective or "").strip(),
    }


def _draft_to_schema_steps(draft: dict) -> list[CaseStepJson]:
    return [
        CaseStepJson(order=s.get("order", 1), description=s.get("description", ""), expected=s.get("expected", ""))
        for s in draft.get("steps", [])
    ]


class GeneratedCaseDraft:
    """路由层使用的草稿结构（与原先 case_generator 字段对齐）。"""

    def __init__(self, draft: dict) -> None:
        self.title = draft.get("title", "")
        self.preconditions = draft.get("preconditions", "")
        self.steps = _draft_to_schema_steps(draft)
        self.task_text = draft.get("task_text", "")
        self.priority = draft.get("priority", "P2")
        self.model = draft.get("model", "")
        self.similar_case_ids = draft.get("similar_case_ids")
        self.rag_trace = draft.get("rag_trace")


def build_draft_from_agent_dict(draft: GeneratedCaseDraft) -> dict:
    """序列化为 API 响应 dict。"""
    from app.schemas import CaseGenerateMetaOut, CaseStepJson, TestCaseGenerateOut

    return TestCaseGenerateOut(
        title=draft.title,
        task_text=draft.task_text,
        preconditions=draft.preconditions,
        steps=[CaseStepJson(order=s.order, description=s.description, expected=s.expected) for s in draft.steps],
        priority=draft.priority,
        generation_meta=CaseGenerateMetaOut(
            model=draft.model,
            similar_case_ids=draft.similar_case_ids or [],
            rag_trace=draft.rag_trace or [],
        ),
    ).model_dump()


def generate_case_draft_precheck(
    db: Session,
    *,
    project: Project,
    user: User,
    robot_instance: RobotInstance,
) -> None:
    if not can_use_robot_instance(db, user, robot_instance):
        raise AnalysisAgentError("无权使用该测试分析机器人实例，或实例已停用")
    ok, msg = instance_available_for_generation(db, robot_instance)
    if not ok:
        raise AnalysisAgentError(msg)
