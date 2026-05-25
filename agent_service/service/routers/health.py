"""健康检查。"""

from fastapi import APIRouter

from agent_service.service.task_manager import task_manager

router = APIRouter()


@router.get("/api/agent/health")
async def health():
    return {
        "status": "ok",
        "active_tasks": task_manager.active_count,
    }
