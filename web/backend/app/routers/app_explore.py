"""APP 功能菜单遍历（Midscene + HDC）与 Excel 下载。"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.deps import get_current_user
from app.models import AppExploreRun, RobotInstance, User
from app.schemas import AppExploreRunCreate, AppExploreRunOut, InstalledAppOut
from app.services.hdc_apps import list_installed_harmony_apps
from app.services.app_explore_service import (
    execute_app_explore_run,
    explore_busy_message,
    find_active_explore_for_instance,
    prepare_explore_cancel_slot,
    signal_explore_cancel,
)
from app.services.company_scope import can_use_robot_instance
from app.services.robot_run_guard import (
    busy_run_detail_message,
    find_active_run_for_instance,
)

router = APIRouter(prefix="/app-explore", tags=["app-explore"])

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="app_explore")


def _run_in_thread(run_id: int) -> None:
    db = SessionLocal()
    try:
        execute_app_explore_run(db, run_id)
    finally:
        db.close()


@router.get("/installed-apps", response_model=list[InstalledAppOut])
def list_installed_apps(
    _user: User = Depends(get_current_user),
) -> list[InstalledAppOut]:
    """列出设备已安装应用（hdc shell bm dump -a -l，含中文显示名）。"""
    try:
        entries = list_installed_harmony_apps()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_UNAVAILABLE,
            detail=f"无法获取已安装应用列表：{e}",
        ) from e
    return [InstalledAppOut(bundle_id=b, label=label) for b, label in entries]


@router.post("/runs", response_model=AppExploreRunOut, status_code=status.HTTP_201_CREATED)
async def start_explore(
    body: AppExploreRunCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AppExploreRun:
    inst = db.query(RobotInstance).filter(RobotInstance.id == body.robot_instance_id).first()
    if inst is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="机器人实例不存在")
    if not can_use_robot_instance(db, user, inst):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权使用该机器人实例",
        )

    backend = (inst.test_agent_backend or "autoglm").strip().lower()
    if backend != "midscene":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="功能探索仅支持 Midscene（HarmonyOS/HDC）机器人，请将实例 test_agent_backend 设为 midscene",
        )

    busy_test = find_active_run_for_instance(db, inst.id)
    if busy_test is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=busy_run_detail_message(busy_test),
        )

    busy = find_active_explore_for_instance(db, inst.id)
    if busy is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=explore_busy_message(busy),
        )

    bundle_id = body.bundle_id.strip()
    if not bundle_id or "." not in bundle_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请填写有效的 APP ID（与 hdc shell bm dump -a 中的 bundleName 一致）",
        )

    app_name = (body.app_name or bundle_id).strip()[:256]

    run = AppExploreRun(
        owner_id=user.id,
        robot_instance_id=inst.id,
        bundle_id=bundle_id[:256],
        app_name=app_name,
        max_screens=body.max_screens,
        max_depth=body.max_depth,
        status="pending",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    prepare_explore_cancel_slot(run.id)
    asyncio.get_running_loop().run_in_executor(_executor, _run_in_thread, run.id)
    return run


@router.get("/runs/{run_id}", response_model=AppExploreRunOut)
def get_explore_run(
    run_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AppExploreRun:
    run = db.query(AppExploreRun).filter(AppExploreRun.id == run_id).first()
    if run is None or run.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="探索任务不存在")
    return run


@router.post("/runs/{run_id}/cancel", response_model=AppExploreRunOut)
def cancel_explore_run(
    run_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AppExploreRun:
    run = db.query(AppExploreRun).filter(AppExploreRun.id == run_id).first()
    if run is None or run.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="探索任务不存在")
    if run.status not in ("pending", "running"):
        return run
    signal_explore_cancel(run_id)
    run.status = "cancelled"
    run.output_message = "用户已请求取消"
    db.commit()
    db.refresh(run)
    return run


@router.get("/runs/{run_id}/download")
def download_explore_excel(
    run_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    run = db.query(AppExploreRun).filter(AppExploreRun.id == run_id).first()
    if run is None or run.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="探索任务不存在")

    path_str = (run.excel_path or "").strip()
    if not path_str:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Excel 尚未生成，请等待探索完成或查看任务失败原因",
        )
    path = Path(path_str)
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Excel 文件不存在")

    safe_name = f"{run.app_name or run.bundle_id}-功能清单.xlsx".replace("/", "_")
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=safe_name,
    )
