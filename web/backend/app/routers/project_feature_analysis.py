"""项目功能点分析：测试分析机器人 + 真机遍历 + 功能树确认。"""

from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.deps import get_current_user
from app.models import (
    ProjectAppArtifact,
    ProjectFeatureAnalysisRun,
    ProjectFeatureTree,
    RobotInstance,
    User,
)
from app.routers.project_functional import (
    _max_upload_bytes,
    _safe_filename,
    _upload_root,
)
from app.routers.projects import _require_project, _require_project_owner
from app.schemas import (
    AppInstallIn,
    AppInstallOut,
    FeatureAnalysisRunCreate,
    FeatureAnalysisRunOut,
    FeatureAnalysisTreeConfirmIn,
    FeatureAnalysisTreeOut,
    FeatureAnalysisTreeUpdateIn,
    InstalledAppOut,
    InstalledAppsCatalogOut,
    ProjectAppArtifactOut,
)
from app.services.app_install import install_package_file, list_installed_apps
from app.services.device_discovery import list_connected_devices
from app.services.package_bundle import resolve_bundle_after_install
from app.services.installed_apps_catalog import build_installed_apps_catalog
from app.services.company_scope import can_use_robot_instance, project_scope_query
from app.services.package_platform import (
    infer_device_platform_from_package,
    parse_platform_app_text,
)
from app.services.feature_analysis_guard import instance_available_for_feature_analysis
from app.services.feature_analysis_service import (
    execute_feature_analysis_run,
    prepare_feature_cancel_slot,
    signal_feature_cancel,
)
from app.services.robot_catalog import is_analysis_catalog

router = APIRouter(prefix="/projects", tags=["project-feature-analysis"])

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="feature_analysis")


def _run_in_thread(run_id: int) -> None:
    db = SessionLocal()
    try:
        execute_feature_analysis_run(db, run_id)
    finally:
        db.close()


def _artifact_path(art: ProjectAppArtifact) -> Path:
    return _upload_root() / art.storage_key


@router.get(
    "/{project_id}/feature-analysis/installed-apps-catalog",
    response_model=InstalledAppsCatalogOut,
)
def list_installed_apps_catalog(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> InstalledAppsCatalogOut:
    """按平台（鸿蒙 / Android）分别枚举在线设备及已安装应用。"""
    _require_project(db, project_id, user)
    return build_installed_apps_catalog()


@router.get("/{project_id}/feature-analysis/installed-apps", response_model=list[InstalledAppOut])
def list_installed_apps_for_project(
    project_id: int,
    platform: str = "harmonyos",
    device_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[InstalledAppOut]:
    _require_project(db, project_id, user)
    try:
        entries = list_installed_apps(platform, device_id=device_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"无法获取已安装应用列表：{e}",
        ) from e
    return [InstalledAppOut(bundle_id=b, label=label) for b, label in entries]


@router.get("/{project_id}/feature-analysis/app-packages", response_model=list[ProjectAppArtifactOut])
def list_feature_app_packages(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ProjectAppArtifact]:
    _require_project(db, project_id, user)
    return (
        db.query(ProjectAppArtifact)
        .filter(ProjectAppArtifact.project_id == project_id)
        .order_by(ProjectAppArtifact.created_at.desc())
        .all()
    )


@router.post("/{project_id}/feature-analysis/app-packages", response_model=ProjectAppArtifactOut)
async def upload_feature_app_package(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    file: UploadFile = File(...),
) -> ProjectAppArtifact:
    import uuid

    _require_project_owner(db, project_id, user)
    data = await file.read()
    mx = _max_upload_bytes()
    if len(data) > mx:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="安装包超过大小限制")
    root = _upload_root()
    root.mkdir(parents=True, exist_ok=True)
    ext = Path(_safe_filename(file.filename or "")).suffix.lower() or ".apk"
    if ext not in (".apk", ".aab", ".hap", ".app", ".bin", ".zip"):
        ext = ".apk"
    key = f"{project_id}/{uuid.uuid4().hex}{ext}"
    dest = root / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    row = ProjectAppArtifact(
        project_id=project_id,
        owner_id=user.id,
        filename=_safe_filename(file.filename or key),
        storage_key=key,
        size_bytes=len(data),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post(
    "/{project_id}/feature-analysis/app-packages/{artifact_id}/install",
    response_model=AppInstallOut,
)
def install_feature_app_package(
    project_id: int,
    artifact_id: int,
    body: AppInstallIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AppInstallOut:
    _require_project_owner(db, project_id, user)
    art = (
        db.query(ProjectAppArtifact)
        .filter(
            ProjectAppArtifact.id == artifact_id,
            ProjectAppArtifact.project_id == project_id,
        )
        .first()
    )
    if art is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="安装包不存在")
    path = _artifact_path(art)
    platform = infer_device_platform_from_package(
        filename=art.filename,
        bundle_id="",
        explicit=body.device_platform,
    )
    device_id = (body.device_id or "").strip() or None
    if not device_id:
        try:
            online = [
                d
                for d in list_connected_devices(platform)
                if (d.state or "").lower() in ("device", "online")
            ]
            device_id = online[0].device_id if online else None
        except RuntimeError:
            device_id = None

    try:
        before_entries = list_installed_apps(platform, device_id=device_id)
        before_ids = {b for b, _ in before_entries}
        msg = install_package_file(path, platform, device_id=device_id)
        after_entries = list_installed_apps(platform, device_id=device_id)
        bundle_id, app_name = resolve_bundle_after_install(
            platform=platform,
            file_path=path,
            before=before_ids,
            after_entries=after_entries,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    from app.services.package_platform import platform_label_cn

    return AppInstallOut(
        ok=True,
        message=msg,
        bundle_id=bundle_id,
        app_display_name=app_name,
        device_platform=platform,
        platform_label=platform_label_cn(platform),
        device_id=device_id,
    )


@router.get("/{project_id}/feature-analysis/runs", response_model=list[FeatureAnalysisRunOut])
def list_feature_runs(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ProjectFeatureAnalysisRun]:
    _require_project(db, project_id, user)
    return (
        db.query(ProjectFeatureAnalysisRun)
        .filter(ProjectFeatureAnalysisRun.project_id == project_id)
        .order_by(desc(ProjectFeatureAnalysisRun.id))
        .limit(50)
        .all()
    )


@router.post(
    "/{project_id}/feature-analysis/runs",
    response_model=FeatureAnalysisRunOut,
    status_code=status.HTTP_201_CREATED,
)
async def start_feature_analysis(
    project_id: int,
    body: FeatureAnalysisRunCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectFeatureAnalysisRun:
    _require_project_owner(db, project_id, user)

    inst = db.query(RobotInstance).filter(RobotInstance.id == body.robot_instance_id).first()
    if inst is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="机器人实例不存在")
    if not can_use_robot_instance(db, user, inst):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权使用该机器人实例")
    if not is_analysis_catalog(inst.catalog_robot_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="功能点分析仅支持测试分析类数字机器人实例",
        )

    ok, msg = instance_available_for_feature_analysis(db, inst)
    if not ok:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg)

    bundle_id = body.bundle_id.strip()
    art_filename = ""

    if body.app_source == "uploaded":
        if not body.app_artifact_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上传安装模式须选择安装包")
        art = (
            db.query(ProjectAppArtifact)
            .filter(
                ProjectAppArtifact.id == body.app_artifact_id,
                ProjectAppArtifact.project_id == project_id,
            )
            .first()
        )
        if art is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="安装包不存在")
        art_filename = art.filename or ""
        platform = infer_device_platform_from_package(
            bundle_id=bundle_id,
            filename=art_filename,
            explicit=body.device_platform,
        )
        app_name = (body.app_display_name or bundle_id).strip()[:256]
        if not bundle_id or "." not in bundle_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="上传安装模式请填写安装后的应用包名",
            )
    else:
        if bundle_id and "." in bundle_id:
            platform = infer_device_platform_from_package(
                bundle_id=bundle_id,
                filename="",
                explicit=body.device_platform,
            )
            app_name = (body.app_display_name or bundle_id).strip()[:256]
        else:
            label = (body.platform_app_text or "").strip()
            if not label:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="请从已安装应用列表中选择应用，或填写平台+应用名",
                )
            try:
                platform, app_name = parse_platform_app_text(label)
            except ValueError as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
            bundle_id = ""
            app_name = app_name[:256]

    run = ProjectFeatureAnalysisRun(
        project_id=project_id,
        owner_id=user.id,
        robot_instance_id=inst.id,
        device_platform=platform,
        device_id=(body.device_id or "").strip() or None,
        app_source=body.app_source,
        app_artifact_id=body.app_artifact_id,
        bundle_id=bundle_id[:256],
        app_display_name=app_name,
        max_screens=body.max_screens,
        max_depth=body.max_depth,
        status="pending",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    prepare_feature_cancel_slot(run.id)
    asyncio.get_running_loop().run_in_executor(_executor, _run_in_thread, run.id)
    return run


@router.get("/{project_id}/feature-analysis/runs/{run_id}", response_model=FeatureAnalysisRunOut)
def get_feature_run(
    project_id: int,
    run_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectFeatureAnalysisRun:
    _require_project(db, project_id, user)
    run = (
        db.query(ProjectFeatureAnalysisRun)
        .filter(
            ProjectFeatureAnalysisRun.id == run_id,
            ProjectFeatureAnalysisRun.project_id == project_id,
        )
        .first()
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分析任务不存在")
    return run


@router.post("/{project_id}/feature-analysis/runs/{run_id}/cancel", response_model=FeatureAnalysisRunOut)
def cancel_feature_run(
    project_id: int,
    run_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectFeatureAnalysisRun:
    _require_project_owner(db, project_id, user)
    run = (
        db.query(ProjectFeatureAnalysisRun)
        .filter(
            ProjectFeatureAnalysisRun.id == run_id,
            ProjectFeatureAnalysisRun.project_id == project_id,
        )
        .first()
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分析任务不存在")
    if run.status not in ("pending", "running"):
        return run
    signal_feature_cancel(run_id)
    run.status = "cancelled"
    run.output_message = "用户已请求取消"
    db.commit()
    db.refresh(run)
    return run


@router.get("/{project_id}/feature-analysis/runs/{run_id}/download")
def download_feature_excel(
    project_id: int,
    run_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_project(db, project_id, user)
    run = (
        db.query(ProjectFeatureAnalysisRun)
        .filter(
            ProjectFeatureAnalysisRun.id == run_id,
            ProjectFeatureAnalysisRun.project_id == project_id,
        )
        .first()
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分析任务不存在")
    path_str = (run.excel_path or "").strip()
    if not path_str:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Excel 尚未生成")
    path = Path(path_str)
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Excel 文件不存在")
    safe_name = f"{run.app_display_name or run.bundle_id}-功能菜单树.xlsx".replace("/", "_")
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=safe_name,
    )


@router.post(
    "/{project_id}/feature-analysis/runs/{run_id}/confirm",
    response_model=FeatureAnalysisTreeOut,
    status_code=status.HTTP_201_CREATED,
)
def confirm_feature_tree(
    project_id: int,
    run_id: int,
    body: FeatureAnalysisTreeConfirmIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeatureAnalysisTreeOut:
    _require_project_owner(db, project_id, user)
    run = (
        db.query(ProjectFeatureAnalysisRun)
        .filter(
            ProjectFeatureAnalysisRun.id == run_id,
            ProjectFeatureAnalysisRun.project_id == project_id,
        )
        .first()
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分析任务不存在")
    if run.status != "success":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅成功的分析任务可确认功能树",
        )

    n = (
        db.query(func.count(ProjectFeatureTree.id))
        .filter(ProjectFeatureTree.project_id == project_id)
        .scalar()
        or 0
    )
    label = (body.version_label or "").strip() or f"v{int(n) + 1}"

    tree = ProjectFeatureTree(
        project_id=project_id,
        run_id=run.id,
        owner_id=user.id,
        tree_json=json.dumps(body.tree_json, ensure_ascii=False),
        version_label=label[:64],
    )
    db.add(tree)
    db.commit()
    db.refresh(tree)
    return FeatureAnalysisTreeOut(
        id=tree.id,
        project_id=tree.project_id,
        run_id=tree.run_id,
        owner_id=tree.owner_id,
        tree_json=tree.tree_json,
        version_label=tree.version_label,
        confirmed_at=tree.confirmed_at,
        created_at=tree.created_at,
        app_display_name=run.app_display_name,
        bundle_id=run.bundle_id,
    )


@router.get("/{project_id}/feature-analysis/trees", response_model=list[FeatureAnalysisTreeOut])
def list_feature_trees(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[FeatureAnalysisTreeOut]:
    _require_project(db, project_id, user)
    trees = (
        db.query(ProjectFeatureTree)
        .filter(ProjectFeatureTree.project_id == project_id)
        .order_by(desc(ProjectFeatureTree.confirmed_at))
        .all()
    )
    out: list[FeatureAnalysisTreeOut] = []
    for t in trees:
        run = db.query(ProjectFeatureAnalysisRun).filter(ProjectFeatureAnalysisRun.id == t.run_id).first()
        out.append(
            FeatureAnalysisTreeOut(
                id=t.id,
                project_id=t.project_id,
                run_id=t.run_id,
                owner_id=t.owner_id,
                tree_json=t.tree_json,
                version_label=t.version_label,
                confirmed_at=t.confirmed_at,
                created_at=t.created_at,
                app_display_name=run.app_display_name if run else "",
                bundle_id=run.bundle_id if run else "",
            )
        )
    return out


@router.get("/{project_id}/feature-analysis/trees/{tree_id}", response_model=FeatureAnalysisTreeOut)
def get_feature_tree(
    project_id: int,
    tree_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeatureAnalysisTreeOut:
    _require_project(db, project_id, user)
    t = (
        db.query(ProjectFeatureTree)
        .filter(
            ProjectFeatureTree.id == tree_id,
            ProjectFeatureTree.project_id == project_id,
        )
        .first()
    )
    if t is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="功能树不存在")
    run = db.query(ProjectFeatureAnalysisRun).filter(ProjectFeatureAnalysisRun.id == t.run_id).first()
    return FeatureAnalysisTreeOut(
        id=t.id,
        project_id=t.project_id,
        run_id=t.run_id,
        owner_id=t.owner_id,
        tree_json=t.tree_json,
        version_label=t.version_label,
        confirmed_at=t.confirmed_at,
        created_at=t.created_at,
        app_display_name=run.app_display_name if run else "",
        bundle_id=run.bundle_id if run else "",
    )


@router.patch("/{project_id}/feature-analysis/trees/{tree_id}", response_model=FeatureAnalysisTreeOut)
def update_feature_tree(
    project_id: int,
    tree_id: int,
    body: FeatureAnalysisTreeUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeatureAnalysisTreeOut:
    _require_project_owner(db, project_id, user)
    t = (
        db.query(ProjectFeatureTree)
        .filter(
            ProjectFeatureTree.id == tree_id,
            ProjectFeatureTree.project_id == project_id,
        )
        .first()
    )
    if t is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="功能树不存在")
    t.tree_json = json.dumps(body.tree_json, ensure_ascii=False)
    if body.version_label.strip():
        t.version_label = body.version_label.strip()[:64]
    db.commit()
    db.refresh(t)
    run = db.query(ProjectFeatureAnalysisRun).filter(ProjectFeatureAnalysisRun.id == t.run_id).first()
    return FeatureAnalysisTreeOut(
        id=t.id,
        project_id=t.project_id,
        run_id=t.run_id,
        owner_id=t.owner_id,
        tree_json=t.tree_json,
        version_label=t.version_label,
        confirmed_at=t.confirmed_at,
        created_at=t.created_at,
        app_display_name=run.app_display_name if run else "",
        bundle_id=run.bundle_id if run else "",
    )
