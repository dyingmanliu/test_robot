from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from starlette.requests import Request

# 与 Agent CLI / executor 共用仓库根目录 .env（JWT、数据库路径、大模型 Key 等）
_REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_REPO_ROOT / ".env")

from app.logging_config import configure_logging

configure_logging()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import (
    Base,
    bootstrap_rbac,
    engine,
    ensure_builtin_platform_admin,
    ensure_company_bootstrap,
    ensure_personal_spaces,
    ensure_projects_bootstrap,
    ensure_schema,
)
from app.routers import (
    admin,
    app_explore,
    auth,
    companies,
    billing,
    dashboard,
    device_pools_api,
    devices,
    knowledge,
    marketplace,
    mai_ui,
    monitor_api,
    platform_api,
    project_functional,
    projects,
    rentals,
    robot_instances,
    test_cases,
    ws_monitor,
)

app = FastAPI(title="识图技术数字机器人", version="1.0.0")

_http_log = logging.getLogger("app.http")


def _http_log_level(path: str, method: str) -> int:
    """高频轮询接口可用 LOG_HTTP_QUIET_POLLS=1 降为 DEBUG。"""
    if os.getenv("LOG_HTTP_QUIET_POLLS", "").strip().lower() in ("1", "true", "yes"):
        if method == "GET" and (path.endswith("/health") or "/test-cases/runs/" in path):
            return logging.DEBUG
    return logging.INFO


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
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(companies.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(project_functional.router, prefix="/api")
app.include_router(device_pools_api.router, prefix="/api")
app.include_router(devices.router, prefix="/api")
app.include_router(test_cases.router, prefix="/api")
app.include_router(knowledge.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(platform_api.router, prefix="/api")
app.include_router(marketplace.router, prefix="/api")
app.include_router(rentals.router, prefix="/api")
app.include_router(robot_instances.router, prefix="/api")
app.include_router(billing.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(monitor_api.router, prefix="/api")
app.include_router(mai_ui.router, prefix="/api")
app.include_router(app_explore.router, prefix="/api")
app.include_router(ws_monitor.router, prefix="/api")


_startup_log = logging.getLogger("app")


@app.on_event("startup")
def on_startup() -> None:
    _startup_log.info("应用启动：初始化数据库与 RBAC")
    Base.metadata.create_all(bind=engine)
    ensure_schema()
    ensure_builtin_platform_admin()
    ensure_company_bootstrap()
    ensure_personal_spaces()
    ensure_projects_bootstrap()
    bootstrap_rbac()
    from app.database import SessionLocal
    from app.services.robot_run_guard import reconcile_stale_runs_on_startup

    db = SessionLocal()
    try:
        n = reconcile_stale_runs_on_startup(db)
        if n:
            _startup_log.info("已清理残留执行任务 %s 条", n)
    finally:
        db.close()
    _startup_log.info("应用启动完成")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
