"""项目空间：安装包、用例集与功能测试下发（Kafka 队列）。"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import (
    FunctionalDispatchTask,
    Project,
    ProjectAppArtifact,
    TestCase,
    TestCaseSet,
    TestCaseSetItem,
    User,
)
from app.routers.projects import _require_project_owner
from app.schemas import (
    CaseSetAiDraftOut,
    CaseSetCreate,
    CaseSetOut,
    FunctionalDispatchCreatedOut,
    FunctionalDispatchCreate,
    FunctionalDispatchListOut,
    ProjectAppArtifactOut,
)
from app.services.device_pools import is_known_pool
from app.services.kafka_functional import publish_functional_dispatch

router = APIRouter(prefix="/projects", tags=["project-functional"])

_REPO_ROOT = Path(__file__).resolve().parents[4]


def _upload_root() -> Path:
    raw = os.getenv("TCM_APP_UPLOAD_DIR")
    if raw and raw.strip():
        return Path(raw.strip()).expanduser().resolve()
    return (_REPO_ROOT / "web" / "backend" / "data" / "app_uploads").resolve()


def _max_upload_bytes() -> int:
    mb = int(os.getenv("TCM_APP_UPLOAD_MAX_MB", "200"))
    return max(1, mb) * 1024 * 1024


def _safe_filename(name: str) -> str:
    base = Path(name or "upload").name
    if not base or base in (".", ".."):
        return "package.bin"
    return base[:240]


@router.post("/{project_id}/app-packages", response_model=ProjectAppArtifactOut)
async def upload_app_package(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    file: UploadFile = File(...),
) -> ProjectAppArtifact:
    _require_project_owner(db, project_id, user)
    data = await file.read()
    mx = _max_upload_bytes()
    if len(data) > mx:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="安装包超过大小限制")
    root = _upload_root()
    root.mkdir(parents=True, exist_ok=True)
    ext = Path(_safe_filename(file.filename or "")).suffix.lower() or ".apk"
    if ext not in (".apk", ".aab", ".bin", ".zip"):
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


@router.get("/{project_id}/app-packages", response_model=list[ProjectAppArtifactOut])
def list_app_packages(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ProjectAppArtifact]:
    _require_project_owner(db, project_id, user)
    return (
        db.query(ProjectAppArtifact)
        .filter(ProjectAppArtifact.project_id == project_id)
        .order_by(ProjectAppArtifact.created_at.desc())
        .all()
    )


def _case_ids_for_set(db: Session, set_id: int) -> list[int]:
    rows = (
        db.query(TestCaseSetItem.case_id)
        .filter(TestCaseSetItem.set_id == set_id)
        .order_by(TestCaseSetItem.sort_order, TestCaseSetItem.id)
        .all()
    )
    return [r[0] for r in rows]


@router.post("/{project_id}/case-sets", response_model=CaseSetOut)
def create_case_set(
    project_id: int,
    body: CaseSetCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CaseSetOut:
    _require_project_owner(db, project_id, user)
    seen = set()
    for cid in body.case_ids:
        if cid in seen:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="case_ids 存在重复")
        seen.add(cid)
    cases = (
        db.query(TestCase)
        .filter(TestCase.id.in_(body.case_ids), TestCase.project_id == project_id)
        .all()
    )
    if len(cases) != len(body.case_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="存在不属于该项目的用例")
    s = TestCaseSet(
        project_id=project_id,
        owner_id=user.id,
        name=body.name.strip(),
        description=(body.description or "").strip(),
        ai_assisted=False,
    )
    db.add(s)
    db.flush()
    for i, cid in enumerate(body.case_ids):
        db.add(TestCaseSetItem(set_id=s.id, case_id=cid, sort_order=i))
    db.commit()
    db.refresh(s)
    return CaseSetOut(
        id=s.id,
        project_id=s.project_id,
        name=s.name,
        description=s.description,
        ai_assisted=s.ai_assisted,
        case_ids=_case_ids_for_set(db, s.id),
        created_at=s.created_at,
    )


@router.get("/{project_id}/case-sets", response_model=list[CaseSetOut])
def list_case_sets(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CaseSetOut]:
    _require_project_owner(db, project_id, user)
    sets = db.query(TestCaseSet).filter(TestCaseSet.project_id == project_id).order_by(TestCaseSet.created_at.desc()).all()
    out: list[CaseSetOut] = []
    for s in sets:
        out.append(
            CaseSetOut(
                id=s.id,
                project_id=s.project_id,
                name=s.name,
                description=s.description,
                ai_assisted=s.ai_assisted,
                case_ids=_case_ids_for_set(db, s.id),
                created_at=s.created_at,
            )
        )
    return out


@router.post("/{project_id}/case-sets/ai-draft", response_model=CaseSetAiDraftOut)
def ai_draft_case_set(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CaseSetAiDraftOut:
    """占位：接入大模型后根据项目目标生成用例集草稿。"""
    p = _require_project_owner(db, project_id, user)
    return CaseSetAiDraftOut(
        suggested_name=f"{p.name} · AI 推荐用例集",
        description="（占位）接入模型后将结合测试目标与被测应用自动生成步骤与覆盖建议。",
        message="当前为占位接口：请手动勾选用例或自建集合；后续版本将写回用例集。",
    )


@router.post("/{project_id}/functional-dispatches", response_model=FunctionalDispatchCreatedOut)
def create_functional_dispatch(
    project_id: int,
    body: FunctionalDispatchCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FunctionalDispatchCreatedOut:
    _require_project_owner(db, project_id, user)
    if not is_known_pool(body.device_pool_id.strip()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的设备池")

    art = (
        db.query(ProjectAppArtifact)
        .filter(ProjectAppArtifact.id == body.app_artifact_id, ProjectAppArtifact.project_id == project_id)
        .first()
    )
    if art is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="安装包不存在")

    cs = (
        db.query(TestCaseSet)
        .filter(TestCaseSet.id == body.case_set_id, TestCaseSet.project_id == project_id)
        .first()
    )
    if cs is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用例集不存在")

    case_ids = _case_ids_for_set(db, cs.id)
    if not case_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用例集为空")

    cases = db.query(TestCase).filter(TestCase.id.in_(case_ids)).all()
    case_map = {c.id: c for c in cases}

    payload = {
        "schema_version": 1,
        "task_kind": "functional_dispatch",
        "robot_kind": "functional_execution",
        "project_id": project_id,
        "owner_id": user.id,
        "app": {
            "artifact_id": art.id,
            "filename": art.filename,
            "storage_key": art.storage_key,
            "size_bytes": art.size_bytes,
        },
        "case_set": {
            "id": cs.id,
            "name": cs.name,
            "case_ids": case_ids,
            "cases": [
                {
                    "id": cid,
                    "title": case_map[cid].title,
                    "task_text": case_map[cid].task_text,
                }
                for cid in case_ids
                if cid in case_map
            ],
        },
        "device_pool_id": body.device_pool_id.strip(),
    }

    task = FunctionalDispatchTask(
        project_id=project_id,
        owner_id=user.id,
        app_artifact_id=art.id,
        case_set_id=cs.id,
        device_pool_id=body.device_pool_id.strip(),
        status="queued",
        payload_snapshot="{}",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    payload["task_id"] = task.id
    task.payload_snapshot = json.dumps(payload, ensure_ascii=False)
    db.commit()

    ok, topic, err, offset = publish_functional_dispatch(payload)
    if ok:
        task.status = "kafka_sent"
        task.kafka_topic = topic
        task.kafka_offset = str(offset) if offset is not None else None
        msg = "任务已写入 Kafka，Agent 管理服务将拉取并分配给功能测试执行数字机器人"
    elif err:
        task.status = "kafka_failed"
        task.kafka_topic = topic
        task.broker_error = err[:8000]
        msg = f"任务已落库，但 Kafka 投递失败：{err[:200]}"
    else:
        task.status = "queued_local"
        msg = "任务已落库；未配置 Kafka（KAFKA_BOOTSTRAP_SERVERS），请配置后由调度层消费"

    db.commit()
    db.refresh(task)

    return FunctionalDispatchCreatedOut(
        id=task.id,
        project_id=task.project_id,
        status=task.status,
        kafka_delivered=ok,
        kafka_topic=task.kafka_topic,
        kafka_offset=task.kafka_offset,
        broker_error=task.broker_error,
        message=msg,
        created_at=task.created_at,
    )


@router.get("/{project_id}/functional-dispatches", response_model=list[FunctionalDispatchListOut])
def list_functional_dispatches(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[FunctionalDispatchTask]:
    _require_project_owner(db, project_id, user)
    return (
        db.query(FunctionalDispatchTask)
        .filter(FunctionalDispatchTask.project_id == project_id)
        .order_by(FunctionalDispatchTask.created_at.desc())
        .limit(100)
        .all()
    )
