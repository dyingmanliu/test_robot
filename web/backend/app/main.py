from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

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
    auth,
    companies,
    billing,
    dashboard,
    device_pools_api,
    devices,
    knowledge,
    marketplace,
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
app.include_router(ws_monitor.router, prefix="/api")


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_schema()
    ensure_builtin_platform_admin()
    ensure_company_bootstrap()
    ensure_personal_spaces()
    ensure_projects_bootstrap()
    bootstrap_rbac()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
