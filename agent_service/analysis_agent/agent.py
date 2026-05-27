"""用例分析 / 编写 Agent：一句话 → structured 测试用例草稿（LangChain CaseGenChain）。"""

from __future__ import annotations

from agent_service.analysis_agent.config import AnalysisAgentConfig, load_analysis_config
from agent_service.analysis_agent.types import CaseDraft, ProjectContext
from agent_service.langchain_platform.chains.case_generation import CaseGenChain


class AnalysisAgent:
    """用例生成门面，委托 langchain_platform CaseGenChain。"""

    def __init__(self, config: AnalysisAgentConfig | None = None) -> None:
        self.config = config or load_analysis_config()
        self._chain = CaseGenChain(self.config)

    def generate_case_draft(
        self,
        *,
        project: ProjectContext,
        prompt: str,
        kb_snippets: list[str] | None = None,
        project_id: int | None = None,
        owner_scope_ids: str | None = None,
    ) -> CaseDraft:
        """根据一句话生成 structured 用例草稿（不写库）。"""
        return self._chain.generate(
            project=project,
            prompt=prompt,
            kb_snippets=kb_snippets,
            project_id=project_id,
            owner_scope_ids=owner_scope_ids,
        )
