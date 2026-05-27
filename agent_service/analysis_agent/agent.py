"""用例分析 / 编写 Agent：Agentic RAG + structured 测试用例草稿。"""

from __future__ import annotations

import os

from agent_service.analysis_agent.config import AnalysisAgentConfig, load_analysis_config
from agent_service.analysis_agent.types import CaseDraft, ProjectContext
from agent_service.langchain_platform.chains.case_generation import CaseGenChain
from agent_service.langchain_platform.graphs.case_gen_agentic import run_case_gen_agentic


class AnalysisAgent:
    """用例生成门面。"""

    def __init__(self, config: AnalysisAgentConfig | None = None) -> None:
        self.config = config or load_analysis_config()
        self._chain = CaseGenChain(self.config)
        self._rag_trace: list = []

    @property
    def rag_trace(self) -> list:
        return self._rag_trace

    def generate_case_draft(
        self,
        *,
        project: ProjectContext,
        prompt: str,
        kb_snippets: list[str] | None = None,
        project_id: int | None = None,
        owner_scope_ids: str | None = None,
        robot_instance_id: int | None = None,
        rag_mode: str | None = None,
    ) -> CaseDraft:
        mode = (rag_mode or os.getenv("RAG_DEFAULT_MODE") or "agentic").strip().lower()
        if mode == "agentic" or robot_instance_id is not None:
            draft, trace = run_case_gen_agentic(
                project=project,
                prompt=prompt,
                robot_instance_id=robot_instance_id,
                project_id=project_id,
                owner_scope_ids=owner_scope_ids,
                rag_mode=mode,
                config=self.config,
            )
            self._rag_trace = trace
            return draft
        self._rag_trace = []
        return self._chain.generate(
            project=project,
            prompt=prompt,
            kb_snippets=kb_snippets,
            project_id=project_id,
            owner_scope_ids=owner_scope_ids,
        )
