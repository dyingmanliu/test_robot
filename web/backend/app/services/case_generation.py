"""Web 适配层：组装 ORM / KB 上下文，调用 analysis_agent（同进程，对齐 executor → autoglm_phone_agent）。"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

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

_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from analysis_agent import AnalysisAgent, AnalysisAgentError, CaseDraft, ProjectContext
from analysis_agent.config import kb_enabled, kb_limit

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
) -> tuple[list[str], list[int]]:
    scope = _kb_owner_scope(db, user)
    rows = search_cases_kb(
        db,
        q=prompt[:200],
        project_id=project.id,
        owner_scope_ids=scope,
        limit=kb_limit(),
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


def _project_context(project: Project) -> ProjectContext:
    return ProjectContext(
        name=project.name,
        tested_app_name=project.tested_app_name or "",
        test_objective=(project.test_objective or "").strip(),
    )


def _draft_to_schema_steps(draft: CaseDraft) -> list[CaseStepJson]:
    return [
        CaseStepJson(order=s.order, description=s.description, expected=s.expected)
        for s in draft.steps
    ]


class GeneratedCaseDraft:
    """路由层使用的草稿结构（与原先 case_generator 字段对齐）。"""

    def __init__(self, draft: CaseDraft) -> None:
        self.title = draft.title
        self.preconditions = draft.preconditions
        self.steps = _draft_to_schema_steps(draft)
        self.task_text = draft.task_text
        self.priority = draft.priority
        self.case_format = getattr(draft, "case_format", None) or "structured"
        self.case_yaml = ""
        self.model = draft.model
        self.similar_case_ids = draft.similar_case_ids


def generate_case_draft(
    db: Session,
    *,
    project: Project,
    user: User,
    robot_instance: RobotInstance,
    prompt: str,
    case_format: str = "structured",
) -> GeneratedCaseDraft:
    if not can_use_robot_instance(db, user, robot_instance):
        raise AnalysisAgentError("无权使用该测试分析机器人实例，或实例已停用")
    ok, msg = instance_available_for_generation(db, robot_instance)
    if not ok:
        raise AnalysisAgentError(msg)
    kb_snippets: list[str] = []
    similar_ids: list[int] = []
    if kb_enabled():
        kb_snippets, similar_ids = _fetch_kb_examples(
            db, project=project, user=user, prompt=prompt
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
    try:
        with analysis_generation_lock(robot_instance.id):
            agent = AnalysisAgent()
            draft = agent.generate_case_draft(
                project=_project_context(project),
                prompt=prompt,
                kb_snippets=kb_snippets,
            )
    except RuntimeError as e:
        if str(e) == "analysis_instance_busy":
            raise AnalysisAgentError(
                "该测试分析机器人正在生成用例，请等待当前任务完成后再试"
            ) from e
        raise
    draft.similar_case_ids = similar_ids or None
    log.info(
        "用例生成完成 project_id=%s title=%r steps=%s model=%s",
        project.id,
        draft.title,
        len(draft.steps),
        draft.model,
    )
    out = GeneratedCaseDraft(draft)
    if (case_format or "structured").strip().lower() == "yaml":
        from app.services.case_format_convert import structured_to_yaml

        out.case_format = "yaml"
        out.case_yaml = structured_to_yaml(
            title=out.title,
            preconditions=out.preconditions,
            steps=out.steps,
            task_text=out.task_text,
        )
    return out
