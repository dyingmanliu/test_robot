"""agent_service FastAPI 应用。"""

from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 确保 repo 根目录在 sys.path 中
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# 本地 .env 加载
_LOCAL_ENV = Path(__file__).resolve().parents[1] / ".env"  # agent_service/.env
load_dotenv(_LOCAL_ENV)

from agent_service.service.config import CLEANUP_INTERVAL_SECONDS, TASK_TTL_SECONDS
from agent_service.service.task_manager import task_manager

from agent_service.service.routers import (
    analysis,
    explore,
    func_agent,
    health,
    midscene,
    tree,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("agent_service")


async def _cleanup_loop():
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
        task_manager.cleanup_expired(TASK_TTL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("agent_service 启动，清理任务每 %ds 执行一次", CLEANUP_INTERVAL_SECONDS)
    cleanup_task = asyncio.create_task(_cleanup_loop())
    yield
    cleanup_task.cancel()
    log.info("agent_service 关闭")


app = FastAPI(
    title="Agent Service",
    description="测试执行 & 分析设计智能体 Web 服务",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(analysis.router)
app.include_router(func_agent.router)
app.include_router(explore.router)
app.include_router(midscene.router)
app.include_router(tree.router)
