"""agent_service FastAPI 应用。"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from starlette.requests import Request

# 确保 repo 根目录在 sys.path 中
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# 本地 .env 加载
_LOCAL_ENV = Path(__file__).resolve().parents[1] / ".env"  # agent_service/.env
load_dotenv(_LOCAL_ENV)

from agent_service.langchain_platform.config import configure_langsmith, langchain_tracing_enabled
from agent_service.service.logging_config import configure_logging

configure_langsmith()
configure_logging()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

log = logging.getLogger("agent_service")
_http_log = logging.getLogger("agent_service.http")


def _http_log_level(path: str, method: str) -> int:
    """健康检查与 SSE 长连接可用 LOG_HTTP_QUIET_POLLS=1 降为 DEBUG。"""
    if os.getenv("LOG_HTTP_QUIET_POLLS", "").strip().lower() in ("1", "true", "yes"):
        if method == "GET" and (
            path.endswith("/health")
            or path.endswith("/stream")
        ):
            return logging.DEBUG
    return logging.INFO


async def _cleanup_loop():
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
        task_manager.cleanup_expired(TASK_TTL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if langchain_tracing_enabled():
        from agent_service.langchain_platform.config import langsmith_project

        log.info("LangSmith 追踪已启用 project=%s", langsmith_project())
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


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start = time.perf_counter()
    method = request.method
    path = request.url.path
    query = str(request.url.query) if request.url.query else ""
    client = request.client.host if request.client else "-"
    try:
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        msg = f"{method} {path}"
        if query and os.getenv("LOG_HTTP_QUERY", "1").strip().lower() in ("1", "true", "yes"):
            msg += f"?{query}"
        _http_log.log(
            _http_log_level(path, method),
            "%s | client=%s | status=%s | %.1fms",
            msg,
            client,
            response.status_code,
            elapsed_ms,
        )
        return response
    except Exception:
        elapsed_ms = (time.perf_counter() - start) * 1000
        _http_log.exception(
            "%s %s | client=%s | 未处理异常 | %.1fms",
            method,
            path,
            client,
            elapsed_ms,
        )
        raise


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
