"""AnalysisAgent LangChain 门面。"""
from __future__ import annotations

from agent_service.analysis_agent.types import CaseDraft, ProjectContext
from agent_service.langchain_platform.chains.case_generation import CaseGenChain


def generate_case_draft_langchain(
    *,
    project: ProjectContext,
    prompt: str,
    kb_snippets: list[str] | None = None,
    project_id: int | None = None,
    owner_scope_ids: str | None = None,
) -> CaseDraft:
    return CaseGenChain().generate(
        project=project,
        prompt=prompt,
        kb_snippets=kb_snippets,
        project_id=project_id,
        owner_scope_ids=owner_scope_ids,
    )
