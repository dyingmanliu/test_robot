"""用例生成 & KB 配置接口。"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from agent_service.analysis_agent import AnalysisAgent, AnalysisAgentError, ProjectContext
from agent_service.analysis_agent.config import kb_enabled, kb_limit
from agent_service.service.schemas import (
    CaseGenConfigResponse,
    CaseGenTaskStatusResponse,
    CaseStepBody,
    CancelResponse,
    GenerateCaseDraftRequest,
    GenerateCaseDraftResponse,
    TaskIdResponse,
)
from agent_service.service.sse import SSEEvent
from agent_service.service.task_manager import TaskStatus, task_manager

log = logging.getLogger("agent_service.analysis")

router = APIRouter()


def _draft_to_payload(draft: Any, agent: AnalysisAgent) -> dict[str, Any]:
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
    ).model_dump()


@router.get("/api/agent/config/case-generation", response_model=CaseGenConfigResponse)
async def get_case_gen_config():
    return CaseGenConfigResponse(kb_enabled=kb_enabled(), kb_limit=kb_limit())


@router.post("/api/agent/analysis/generate-case-draft", response_model=TaskIdResponse, status_code=202)
async def submit_generate_case_draft(req: GenerateCaseDraftRequest):
    record = task_manager.create_task()

    def _run(tr: Any) -> None:
        try:
            if tr.cancel_event.is_set():
                tr.status = TaskStatus.CANCELLED
                tr.queue.put_nowait(SSEEvent(event="cancelled", data={"message": "cancelled"}))
                return

            def on_progress(obj: dict[str, Any]) -> None:
                tr.queue.put_nowait(SSEEvent(event="progress", data=obj))

            on_progress(
                {
                    "kind": "case_gen_log",
                    "phase": "agent",
                    "message": "agent_service 已接收任务，开始执行…",
                }
            )
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
                on_progress=on_progress,
            )
            if tr.cancel_event.is_set():
                tr.status = TaskStatus.CANCELLED
                tr.queue.put_nowait(SSEEvent(event="cancelled", data={"message": "cancelled"}))
                return

            payload = _draft_to_payload(draft, agent)
            tr.result = payload
            tr.status = TaskStatus.DONE
            tr.queue.put_nowait(SSEEvent(event="done", data=payload))
        except AnalysisAgentError as e:
            tr.status = TaskStatus.ERROR
            tr.error_detail = str(e)
            tr.queue.put_nowait(
                SSEEvent(
                    event="progress",
                    data={"kind": "case_gen_log", "phase": "error", "message": str(e)},
                )
            )
            tr.queue.put_nowait(SSEEvent(event="error", data={"detail": str(e)}))

    task_manager.run_background(record, _run)
    return TaskIdResponse(task_id=record.task_id)


@router.get(
    "/api/agent/analysis/generate-case-draft/{task_id}",
    response_model=CaseGenTaskStatusResponse,
)
async def get_generate_case_draft_task(task_id: str):
    record = task_manager.get_task(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="task not found")
    return CaseGenTaskStatusResponse(
        status=record.status.value,
        draft=record.result,
        detail=record.error_detail,
    )


@router.get("/api/agent/analysis/generate-case-draft/{task_id}/stream")
async def stream_generate_case_draft(task_id: str):
    record = task_manager.get_task(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="task not found")

    async def _event_generator():
        while True:
            event = await record.queue.get()
            if event is None:
                break
            yield event.format()

    return StreamingResponse(_event_generator(), media_type="text/event-stream")


@router.delete(
    "/api/agent/analysis/generate-case-draft/{task_id}",
    response_model=CancelResponse,
)
async def cancel_generate_case_draft(task_id: str):
    if task_manager.cancel_task(task_id):
        return CancelResponse()
    raise HTTPException(status_code=404, detail="task not found or already finished")
