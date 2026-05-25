"""midscene 直调长任务接口。"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from agent_service.func_agent.backends.midscene.runtime import run_midscene_task
from agent_service.service.schemas import CancelResponse, MidsceneTaskRequest, TaskIdResponse
from agent_service.service.sse import SSEEvent
from agent_service.service.task_manager import TaskStatus, task_manager

log = logging.getLogger("agent_service.midscene")

router = APIRouter()


@router.post("/api/agent/midscene/task", response_model=TaskIdResponse, status_code=202)
async def submit_midscene(req: MidsceneTaskRequest):
    record = task_manager.create_task()

    def _run(tr: Any) -> None:
        def on_machine_line(obj: dict[str, Any]) -> None:
            kind = obj.get("kind", "")
            event_name = "usage" if kind == "model_usage" else "line"
            tr.queue.put_nowait(SSEEvent(event=event_name, data=obj))

        def should_cancel() -> bool:
            return tr.cancel_event.is_set()

        def log_model_usage(obj: dict[str, Any]) -> None:
            pass

        try:
            ok, msg, report_file = run_midscene_task(
                req.dispatch,
                on_machine_line=on_machine_line,
                should_cancel=should_cancel,
                log_model_usage=log_model_usage,
            )
        except Exception as exc:
            tr.status = TaskStatus.ERROR
            tr.queue.put_nowait(SSEEvent(event="error", data={"detail": str(exc)}))
            return

        if should_cancel():
            tr.status = TaskStatus.CANCELLED
            tr.queue.put_nowait(SSEEvent(event="cancelled", data={"message": "exec cancelled"}))
            return

        tr.status = TaskStatus.DONE
        tr.queue.put_nowait(SSEEvent(event="done", data={"ok": ok, "message": msg, "report_file": report_file}))

    task_manager.run_background(record, _run)
    return TaskIdResponse(task_id=record.task_id)


@router.get("/api/agent/midscene/task/{task_id}/stream")
async def stream_midscene(task_id: str):
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


@router.delete("/api/agent/midscene/task/{task_id}", response_model=CancelResponse)
async def cancel_midscene(task_id: str):
    if task_manager.cancel_task(task_id):
        return CancelResponse()
    raise HTTPException(status_code=404, detail="task not found or already finished")
