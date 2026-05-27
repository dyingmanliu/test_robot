"""Web 适配层：组装 ORM / KB 上下文，通过 HTTP 调用 analysis_agent 服务。"""

from __future__ import annotations

import logging

log = logging.getLogger("app.case_generation")
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Project, RobotInstance, User
from app.rbac import can_view_all_cases
from app.schemas import CaseStepJson
from app.services.analysis_instance_guard import (
    analysis_generation_lock,
    instance_available_for_generation,
)
from app.services.case_kb import search_cases_kb
from app.services.company_scope import (
    can_use_robot_instance,
    company_shares_projects_cases,
    enterprise_colleague_user_ids,
)

from app.knowledge.config import rag_default_mode
from app.services.agent_service_client import (
    AgentServiceError,
    generate_case_draft as _agent_generate,
    get_case_gen_config,
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


def generate_case_draft(
    db: Session,
    *,
    project: Project,
    user: User,
    robot_instance: RobotInstance,
    prompt: str,
) -> GeneratedCaseDraft:
    if not can_use_robot_instance(db, user, robot_instance):
        raise AnalysisAgentError("无权使用该测试分析机器人实例，或实例已停用")
    ok, msg = instance_available_for_generation(db, robot_instance)
    if not ok:
        raise AnalysisAgentError(msg)

    config = get_case_gen_config()
    _kb_enabled = config.get("kb_enabled", True)
    _kb_limit = config.get("kb_limit", 3)

    kb_snippets: list[str] = []
    similar_ids: list[int] = []
    rag_mode = rag_default_mode()
    if _kb_enabled and rag_mode != "agentic":
        kb_snippets, similar_ids = _fetch_kb_examples(
            db, project=project, user=user, prompt=prompt, limit=_kb_limit,
        )
        log.info(
            "用例生成 KB 检索 project_id=%s hits=%s",
            project.id,
            len(similar_ids),
        )

    log.info(
        "调用 analysis_agent 生成用例 project_id=%s user_id=%s instance_id=%s prompt_len=%s",
        project.id,
        user.id,
        robot_instance.id,
        len((prompt or "").strip()),
    )
    scope = _kb_owner_scope(db, user)
    owner_scope_str: str | None = None
    if scope is not None:
        owner_scope_str = ",".join(str(i) for i in scope)

    try:
        with analysis_generation_lock(robot_instance.id):
            draft_dict = _agent_generate(
                project=_project_context(project),
                prompt=prompt,
                kb_snippets=kb_snippets if rag_mode != "agentic" else None,
                project_id=project.id,
                owner_scope_ids=owner_scope_str,
                robot_instance_id=robot_instance.id,
                rag_mode=rag_mode,
            )
    except RuntimeError as e:
        if str(e) == "analysis_instance_busy":
            raise AnalysisAgentError(
                "该测试分析机器人正在生成用例，请等待当前任务完成后再试"
            ) from e
        raise
    except AgentServiceError as e:
        raise AnalysisAgentError(str(e)) from e

    agent_similar = draft_dict.get("similar_case_ids")
    if agent_similar:
        draft_dict["similar_case_ids"] = agent_similar
    else:
        draft_dict["similar_case_ids"] = similar_ids or None
    if draft_dict.get("rag_trace") is None:
        draft_dict["rag_trace"] = []
    log.info(
        "用例生成完成 project_id=%s title=%r steps=%s model=%s",
        project.id,
        draft_dict.get("title"),
        len(draft_dict.get("steps", [])),
        draft_dict.get("model"),
    )
    out = GeneratedCaseDraft(draft_dict)
    return out
