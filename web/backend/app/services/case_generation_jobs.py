"""用例生成异步任务（内存 Job + 后台线程消费 agent_service SSE）。"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.knowledge.config import rag_default_mode
from app.models import Project, RobotInstance, User
from app.services.agent_service_client import (
    AgentServiceError,
    cancel_task as cancel_agent_task,
    stream_case_gen_events,
    submit_case_gen_generate,
)
from app.services.analysis_instance_guard import analysis_generation_lock
from app.services.case_generation import (
    AnalysisAgentError,
    GeneratedCaseDraft,
    _fetch_kb_examples,
    _kb_owner_scope,
    _project_context,
    build_draft_from_agent_dict,
)
log = logging.getLogger("app.case_generation_jobs")

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="case_gen")
_lock = threading.Lock()
_jobs: dict[str, "CaseGenerationJob"] = {}
JOB_TTL_SECONDS = 3600


@dataclass
class CaseGenerationJob:
    job_id: str
    user_id: int
    project_id: int
    robot_instance_id: int
    prompt: str
    status: str = "running"  # running | success | failed | cancelled
    progress_message: str = "已提交，正在生成…"
    step_log: str = ""
    draft: dict[str, Any] | None = None
    error: str | None = None
    agent_task_id: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None
    _cancel_requested: bool = False


def _cleanup_expired_unlocked() -> None:
    """调用方已持有 _lock。"""
    cutoff = datetime.utcnow() - timedelta(seconds=JOB_TTL_SECONDS)
    expired = [
        jid
        for jid, j in _jobs.items()
        if j.created_at < cutoff and j.status != "running"
    ]
    for jid in expired:
        del _jobs[jid]


def _cleanup_expired() -> None:
    with _lock:
        _cleanup_expired_unlocked()


def get_job(job_id: str) -> CaseGenerationJob | None:
    with _lock:
        return _jobs.get(job_id)


def _append_job_log(job: CaseGenerationJob, obj: dict[str, Any]) -> None:
    line = json.dumps(obj, ensure_ascii=False, default=str) + "\n"
    with _lock:
        job.step_log = (job.step_log or "") + line
        msg = (obj.get("message") or "").strip()
        if msg:
            job.progress_message = msg


def append_job_log(job_id: str, obj: dict[str, Any]) -> None:
    job = get_job(job_id)
    if job is not None:
        _append_job_log(job, obj)


def start_case_generation_job(
    _db: Session,
    *,
    project: Project,
    user: User,
    robot_instance: RobotInstance,
    prompt: str,
) -> str:
    """立即返回 job_id；预检与 agent 调用在后台线程执行，避免阻塞 HTTP 202。"""

    job_id = uuid.uuid4().hex
    job = CaseGenerationJob(
        job_id=job_id,
        user_id=user.id,
        project_id=project.id,
        robot_instance_id=robot_instance.id,
        prompt=prompt.strip(),
    )
    with _lock:
        _cleanup_expired_unlocked()
        _jobs[job_id] = job
    _append_job_log(
        job,
        {"kind": "case_gen_log", "phase": "submit", "message": "任务已排队，等待后台线程执行…"},
    )
    _executor.submit(_execute_job, job_id)
    log.info(
        "用例生成任务已提交 job_id=%s project_id=%s instance_id=%s",
        job_id,
        project.id,
        robot_instance.id,
    )
    return job_id


def cancel_case_generation_job(job_id: str, *, user_id: int) -> bool:
    job = get_job(job_id)
    if job is None or job.user_id != user_id:
        return False
    if job.status != "running":
        return False
    job._cancel_requested = True
    if job.agent_task_id:
        try:
            cancel_agent_task("case-gen", job.agent_task_id)
        except Exception:
            log.warning("取消 agent 用例生成任务失败 job_id=%s", job_id, exc_info=True)
    job.status = "cancelled"
    job.error = "已取消"
    job.finished_at = datetime.utcnow()
    job.progress_message = "已取消"
    _append_job_log(
        job,
        {"kind": "case_gen_log", "phase": "cancelled", "message": "用户取消生成任务"},
    )
    return True


def _execute_job(job_id: str) -> None:
    from app.database import SessionLocal
    from app.services.case_generation import generate_case_draft_precheck

    run_ctx: _AgentRunContext | None = None
    db = SessionLocal()
    try:
        job = get_job(job_id)
        if job is None:
            return
        project = db.query(Project).filter(Project.id == job.project_id).first()
        user = db.query(User).filter(User.id == job.user_id).first()
        robot_instance = (
            db.query(RobotInstance).filter(RobotInstance.id == job.robot_instance_id).first()
        )
        if project is None or user is None or robot_instance is None:
            job.status = "failed"
            job.error = "项目、用户或机器人实例不存在"
            job.finished_at = datetime.utcnow()
            return
        try:
            generate_case_draft_precheck(
                db, project=project, user=user, robot_instance=robot_instance
            )
        except AnalysisAgentError as e:
            job.status = "failed"
            job.error = str(e)
            job.finished_at = datetime.utcnow()
            _append_job_log(
                job,
                {"kind": "case_gen_log", "phase": "error", "message": str(e)},
            )
            return
        run_ctx = _prepare_agent_run_context(db, job, project=project, user=user)
    finally:
        db.close()

    if run_ctx is None:
        return
    job = get_job(job_id)
    if job is None or job.status != "running":
        return

    try:
        with analysis_generation_lock(job.robot_instance_id):
            _run_with_agent(job, run_ctx)
    except RuntimeError as e:
        if str(e) == "analysis_instance_busy":
            job = get_job(job_id)
            if job:
                job.status = "failed"
                msg = "该测试分析机器人正在生成用例，请等待当前任务完成后再试"
                job.error = msg
                _append_job_log(
                    job,
                    {"kind": "case_gen_log", "phase": "error", "message": msg},
                )
        else:
            raise
    except AnalysisAgentError as e:
        job = get_job(job_id)
        if job and job.status == "running":
            job.status = "failed"
            job.error = str(e)
            _append_job_log(
                job,
                {"kind": "case_gen_log", "phase": "error", "message": str(e)},
            )
    except AgentServiceError as e:
        job = get_job(job_id)
        if job and job.status == "running":
            job.status = "failed"
            job.error = str(e)
            _append_job_log(
                job,
                {"kind": "case_gen_log", "phase": "error", "message": str(e)},
            )
    except Exception as e:
        log.exception("用例生成任务异常 job_id=%s", job_id)
        job = get_job(job_id)
        if job and job.status == "running":
            job.status = "failed"
            job.error = f"用例生成失败: {e}"
            _append_job_log(
                job,
                {"kind": "case_gen_log", "phase": "error", "message": job.error},
            )
    finally:
        job = get_job(job_id)
        if job and job.status == "running":
            job.status = "failed"
            job.error = job.error or "用例生成异常结束"
        if job and job.finished_at is None and job.status != "running":
            job.finished_at = datetime.utcnow()


@dataclass
class _AgentRunContext:
    project_ctx: dict[str, str]
    kb_snippets: list[str]
    similar_ids: list[int]
    owner_scope_str: str | None
    rag_mode: str
    kb_enabled: bool


def _prepare_agent_run_context(
    db: Session, job: CaseGenerationJob, *, project: Project, user: User
) -> _AgentRunContext:
    from app.services.agent_service_client import get_case_gen_config

    config = get_case_gen_config()
    kb_enabled = bool(config.get("kb_enabled", True))
    kb_limit = int(config.get("kb_limit", 3))
    rag_mode = rag_default_mode()

    kb_snippets: list[str] = []
    similar_ids: list[int] = []
    if kb_enabled and rag_mode != "agentic":
        kb_snippets, similar_ids = _fetch_kb_examples(
            db, project=project, user=user, prompt=job.prompt, limit=kb_limit,
        )

    scope = _kb_owner_scope(db, user)
    owner_scope_str: str | None = None
    if scope is not None:
        owner_scope_str = ",".join(str(i) for i in scope)

    return _AgentRunContext(
        project_ctx=_project_context(project),
        kb_snippets=kb_snippets,
        similar_ids=similar_ids,
        owner_scope_str=owner_scope_str,
        rag_mode=rag_mode,
        kb_enabled=kb_enabled,
    )


def _run_with_agent(job: CaseGenerationJob, ctx: _AgentRunContext) -> None:
    if job._cancel_requested:
        job.status = "cancelled"
        job.finished_at = datetime.utcnow()
        return

    _append_job_log(
        job,
        {"kind": "case_gen_log", "phase": "submit", "message": "任务已创建，正在提交 agent_service…"},
    )
    if ctx.kb_enabled and ctx.rag_mode != "agentic" and ctx.kb_snippets:
        _append_job_log(
            job,
            {
                "kind": "case_gen_log",
                "phase": "kb_local",
                "message": f"Web 侧预检索参考用例 {len(ctx.similar_ids)} 条",
                "hits": len(ctx.similar_ids),
            },
        )

    task_id = submit_case_gen_generate(
        ctx.project_ctx,
        job.prompt,
        ctx.kb_snippets if ctx.rag_mode != "agentic" else None,
        project_id=job.project_id,
        owner_scope_ids=ctx.owner_scope_str,
        robot_instance_id=job.robot_instance_id,
        rag_mode=ctx.rag_mode,
    )
    job.agent_task_id = task_id
    _append_job_log(
        job,
        {
            "kind": "case_gen_log",
            "phase": "agent",
            "message": f"已提交 agent 任务 {task_id[:8]}…，等待执行",
            "agent_task_id": task_id,
        },
    )

    draft_dict: dict[str, Any] | None = None
    for event_name, event_data in stream_case_gen_events(task_id):
        if job._cancel_requested:
            cancel_agent_task("case-gen", task_id)
            job.status = "cancelled"
            job.error = "已取消"
            job.finished_at = datetime.utcnow()
            _append_job_log(
                job,
                {"kind": "case_gen_log", "phase": "cancelled", "message": "已取消"},
            )
            return
        if event_name == "progress" and isinstance(event_data, dict):
            if event_data.get("kind") == "case_gen_log" or event_data.get("message"):
                _append_job_log(job, event_data)
        elif event_name == "done":
            draft_dict = event_data
        elif event_name == "error":
            detail = event_data.get("detail") or "agent 用例生成失败"
            job.status = "failed"
            job.error = detail
            job.finished_at = datetime.utcnow()
            _append_job_log(
                job,
                {"kind": "case_gen_log", "phase": "error", "message": detail},
            )
            return
        elif event_name == "cancelled":
            job.status = "cancelled"
            job.error = "已取消"
            job.finished_at = datetime.utcnow()
            _append_job_log(
                job,
                {"kind": "case_gen_log", "phase": "cancelled", "message": "已取消"},
            )
            return

    if draft_dict is None:
        job.status = "failed"
        job.error = "未收到生成结果"
        job.finished_at = datetime.utcnow()
        return

    agent_similar = draft_dict.get("similar_case_ids")
    if not agent_similar:
        draft_dict["similar_case_ids"] = ctx.similar_ids or None
    if draft_dict.get("rag_trace") is None:
        draft_dict["rag_trace"] = []

    draft = GeneratedCaseDraft(draft_dict)
    job.draft = build_draft_from_agent_dict(draft)
    job.status = "success"
    job.progress_message = "生成完成"
    job.finished_at = datetime.utcnow()
    _append_job_log(
        job,
        {
            "kind": "case_gen_log",
            "phase": "done",
            "message": f"生成完成：{draft.title}",
            "title": draft.title,
        },
    )
    log.info("用例生成任务完成 job_id=%s title=%r", job.job_id, draft.title)
