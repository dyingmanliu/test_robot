"""用例生成 & KB 配置接口。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from agent_service.analysis_agent import AnalysisAgent, AnalysisAgentError, ProjectContext
from agent_service.analysis_agent.config import kb_enabled, kb_limit
from agent_service.service.schemas import (
    CaseGenConfigResponse,
    GenerateCaseDraftRequest,
    GenerateCaseDraftResponse,
    CaseStepBody,
)

log = logging.getLogger("agent_service.analysis")

router = APIRouter()


@router.get("/api/agent/config/case-generation", response_model=CaseGenConfigResponse)
async def get_case_gen_config():
    return CaseGenConfigResponse(kb_enabled=kb_enabled(), kb_limit=kb_limit())


@router.post("/api/agent/analysis/generate-case-draft", response_model=GenerateCaseDraftResponse)
async def generate_case_draft(req: GenerateCaseDraftRequest):
    try:
        agent = AnalysisAgent()
        project = ProjectContext(
            name=req.project.name,
            tested_app_name=req.project.tested_app_name,
            test_objective=req.project.test_objective,
        )
        draft = agent.generate_case_draft(
            project=project,
            prompt=req.prompt,
            kb_snippets=req.kb_snippets,
            project_id=req.project_id,
            owner_scope_ids=req.owner_scope_ids,
            robot_instance_id=req.robot_instance_id,
            rag_mode=req.rag_mode,
        )
    except AnalysisAgentError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return GenerateCaseDraftResponse(
        title=draft.title,
        preconditions=draft.preconditions,
        steps=[
            CaseStepBody(order=s.order, description=s.description, expected=s.expected)
            for s in draft.steps
        ],
        task_text=draft.task_text,
        priority=draft.priority,
        case_format=getattr(draft, "case_format", "structured") or "structured",
        model=draft.model,
        similar_case_ids=draft.similar_case_ids,
        rag_trace=getattr(agent, "rag_trace", None),
    )
