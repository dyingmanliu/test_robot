"""func-agent 测试执行长任务接口。"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from agent_service.func_agent.core import FuncAgentDispatch
from agent_service.func_agent.orchestrator import run_func_agent_dispatch
from agent_service.service.schemas import CancelResponse, FuncAgentDispatchRequest, TaskIdResponse
from agent_service.service.sse import SSEEvent
from agent_service.service.task_manager import TaskStatus, task_manager

log = logging.getLogger("agent_service.func_agent")

router = APIRouter()


@router.post("/api/agent/func-agent/dispatch", response_model=TaskIdResponse, status_code=202)
async def submit_dispatch(req: FuncAgentDispatchRequest):
    record = task_manager.create_task()

    def _run(tr: Any) -> None:
        dispatch = FuncAgentDispatch(
            backend=req.backend,
            device_platform=req.device_platform,
            device_id=req.device_id,
            payload=req.payload,
        )

        def on_autoglm_step(step_no: int, result: Any) -> None:
            data = asdict(result) if hasattr(result, "__dataclass_fields__") else result
            tr.queue.put_nowait(SSEEvent(event="step", data={"step_no": step_no, "result": data}))

        def on_midscene_line(obj: dict[str, Any]) -> None:
            kind = obj.get("kind", "")
            event_name = "usage" if kind == "model_usage" else "line"
            tr.queue.put_nowait(SSEEvent(event=event_name, data=obj))

        def log_midscene_usage(obj: dict[str, Any]) -> None:
            pass  # usage 已通过 on_midscene_line 推送

        def should_cancel() -> bool:
            return tr.cancel_event.is_set()

        try:
            result = run_func_agent_dispatch(
                dispatch,
                on_autoglm_step=on_autoglm_step,
                on_midscene_line=on_midscene_line,
                should_cancel=should_cancel,
                log_midscene_usage=log_midscene_usage,
            )
        except Exception as exc:
            tr.status = TaskStatus.ERROR
            tr.queue.put_nowait(SSEEvent(event="error", data={"detail": str(exc)}))
            return

        if should_cancel():
            tr.status = TaskStatus.CANCELLED
            tr.queue.put_nowait(SSEEvent(event="cancelled", data={"message": "exec cancelled"}))
            return

        if isinstance(result, tuple):
            ok, msg, report_file = result
        else:
            ok, msg = result.ok, result.message
            report_file = None

        tr.status = TaskStatus.DONE
        tr.queue.put_nowait(SSEEvent(event="done", data={"ok": ok, "message": msg, "report_file": report_file}))

    task_manager.run_background(record, _run)
    return TaskIdResponse(task_id=record.task_id)


@router.get("/api/agent/func-agent/dispatch/{task_id}/stream")
async def stream_dispatch(task_id: str):
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


@router.delete("/api/agent/func-agent/dispatch/{task_id}", response_model=CancelResponse)
async def cancel_dispatch(task_id: str):
    if task_manager.cancel_task(task_id):
        return CancelResponse()
    raise HTTPException(status_code=404, detail="task not found or already finished")
