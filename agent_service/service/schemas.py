"""Pydantic 请求/响应模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ── 同步接口 ──────────────────────────────────────────────


class ProjectContextBody(BaseModel):
    name: str
    tested_app_name: str = ""
    test_objective: str = ""


class GenerateCaseDraftRequest(BaseModel):
    project: ProjectContextBody
    prompt: str
    kb_snippets: list[str] | None = None
    project_id: int | None = None
    owner_scope_ids: str | None = None


class CaseStepBody(BaseModel):
    order: int = 1
    description: str = ""
    expected: str = ""


class GenerateCaseDraftResponse(BaseModel):
    title: str
    preconditions: str = ""
    steps: list[CaseStepBody] = Field(default_factory=list)
    task_text: str = ""
    priority: str = "P2"
    case_format: str = "structured"
    model: str = ""
    similar_case_ids: list[int] | None = None


class CaseGenConfigResponse(BaseModel):
    kb_enabled: bool
    kb_limit: int


class SyncGiicRequest(BaseModel):
    tree_json: dict[str, Any]


class BuildFunctionTreeRequest(BaseModel):
    app_name: str
    features: list[dict[str, Any]]


# ── 异步任务接口 ──────────────────────────────────────────


class TaskIdResponse(BaseModel):
    task_id: str


class CancelResponse(BaseModel):
    status: str = "cancel_requested"


# ── func-agent dispatch ───────────────────────────────────


class FuncAgentDispatchRequest(BaseModel):
    backend: str = "autoglm"
    device_platform: str = "android"
    device_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


# ── explore ───────────────────────────────────────────────


class ExploreRunRequest(BaseModel):
    device_platform: str = "android"
    device_id: str = ""
    app_name: str = ""
    bundle_id: str = ""
    max_screens: int = 1000
    max_depth: int = 5
    traverse_mode: str = "hybrid"
    bfs_max_depth: int = 1
    fair_share_per_root: int = 0
    scroll_reveal_menus: bool = True
    scroll_max_passes: int = 5
    run_id: int | None = None
    robot_instance_id: int | None = None


# ── midscene task ─────────────────────────────────────────


class MidsceneTaskRequest(BaseModel):
    dispatch: dict[str, Any] = Field(default_factory=dict)
