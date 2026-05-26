"""应用探索长任务接口。"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from agent_service.analysis_agent.feature_explore import ExploreDispatch, FeatureExploreAgent
from agent_service.analysis_agent.feature_explore.tree_build import ensure_giic_tree
from agent_service.service.schemas import CancelResponse, ExploreRunRequest, TaskIdResponse
from agent_service.service.sse import SSEEvent
from agent_service.service.task_manager import TaskStatus, task_manager

log = logging.getLogger("agent_service.explore")

router = APIRouter()


@router.post("/api/agent/explore/run", response_model=TaskIdResponse, status_code=202)
async def submit_explore(req: ExploreRunRequest):
    record = task_manager.create_task()

    def _run(tr: Any) -> None:
        dispatch = ExploreDispatch(
            device_platform=req.device_platform,
            device_id=req.device_id,
            app_name=req.app_name,
            bundle_id=req.bundle_id,
            max_screens=req.max_screens,
            max_depth=req.max_depth,
            traverse_mode=req.traverse_mode,
            bfs_max_depth=req.bfs_max_depth,
            fair_share_per_root=req.fair_share_per_root,
            scroll_reveal_menus=req.scroll_reveal_menus,
            scroll_max_passes=req.scroll_max_passes,
            run_id=req.run_id,
            robot_instance_id=req.robot_instance_id,
        )

        def on_machine_line(obj: dict[str, Any]) -> None:
            kind = obj.get("kind", "")
            event_name = "usage" if kind == "model_usage" else "line"
            tr.queue.put_nowait(SSEEvent(event=event_name, data=obj))

        def should_cancel() -> bool:
            return tr.cancel_event.is_set()

        def log_model_usage(obj: dict[str, Any]) -> None:
            pass  # usage 已通过 on_machine_line 推送

        agent = FeatureExploreAgent()
        result = agent.run(
            dispatch,
            on_machine_line=on_machine_line,
            should_cancel=should_cancel,
            log_model_usage=log_model_usage,
        )

        if should_cancel():
            tr.status = TaskStatus.CANCELLED
            tr.queue.put_nowait(SSEEvent(event="cancelled", data={"message": "exec cancelled"}))
            return

        tree = result.tree
        if tree is not None:
            tree = ensure_giic_tree(tree)

        tr.status = TaskStatus.DONE
        tr.queue.put_nowait(SSEEvent(
            event="done",
            data={"ok": result.ok, "message": result.message, "tree": tree, "report_file": result.report_file},
        ))

    task_manager.run_background(record, _run)
    return TaskIdResponse(task_id=record.task_id)


@router.get("/api/agent/explore/run/{task_id}/stream")
async def stream_explore(task_id: str):
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


@router.delete("/api/agent/explore/run/{task_id}", response_model=CancelResponse)
async def cancel_explore(task_id: str):
    if task_manager.cancel_task(task_id):
        return CancelResponse()
    raise HTTPException(status_code=404, detail="task not found or already finished")
