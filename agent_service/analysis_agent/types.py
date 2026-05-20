"""分析 Agent 领域类型（与 Web ORM / Pydantic 解耦）。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProjectContext:
    """项目空间上下文，由 Web 层从 ORM 组装后传入。"""

    name: str
    tested_app_name: str = ""
    test_objective: str = ""


@dataclass
class CaseStep:
    order: int = 1
    description: str = ""
    expected: str = ""


@dataclass
class CaseDraft:
    """structured 用例草稿（不写库）。"""

    title: str
    preconditions: str = ""
    steps: list[CaseStep] = field(default_factory=list)
    task_text: str = ""
    priority: str = "P2"
    case_format: str = "structured"
    model: str = ""
    similar_case_ids: list[int] | None = None
