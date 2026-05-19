from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.executor import execute_test_run, prepare_cancel_slot, signal_cancel
from app.models import Project, RobotInstance, TestCase, TestCaseRevision, TestRun, User
from app.rbac import can_view_all_cases, case_scope_filter, run_scope_query
from app.services.company_scope import can_use_robot_instance, project_readable_by_user
from app.schemas import (
    CaseFormatConvertIn,
    CaseFormatConvertOut,
    CaseGenerateMetaOut,
    CaseImportResultOut,
    CaseStepJson,
    TestCaseCreate,
    TestCaseGenerateIn,
    TestCaseGenerateOut,
    TestCaseOut,
    TestCaseRevisionOut,
    TestCaseUpdate,
    TestRunListItemOut,
    TestRunOut,
    RunCaseBody,
)
from app.services.case_format_convert import structured_to_yaml, yaml_to_structured
from app.services.case_generation import CaseGeneratorError, generate_case_draft
from app.services.case_agent_text import parse_steps_json
from app.services.case_import import parse_import_file, row_to_create
from app.services.robot_run_guard import busy_run_detail_message, find_active_run_for_instance
from app.services.run_report import resolve_report_file
from app.services.case_kb import upsert_case_kb
from app.services.run_metrics import count_recognition_steps
from app.test_case_io import revision_to_out, steps_to_json, test_case_to_out

router = APIRouter(prefix="/test-cases", tags=["test-cases"])

log = logging.getLogger("app.routers.test_cases")

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="tcm_run")


def _run_in_thread(run_id: int) -> None:
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        execute_test_run(db, run_id)
    finally:
        db.close()


def _get_case_for_read(db: Session, case_id: int, user: User) -> TestCase | None:
    q = db.query(TestCase).filter(TestCase.id == case_id)
    if can_view_all_cases(user):
        return q.first()
    return case_scope_filter(db, q, user).first()


def _get_case_for_write(db: Session, case_id: int, user: User) -> TestCase | None:
    q = db.query(TestCase).filter(TestCase.id == case_id)
    if not can_view_all_cases(user):
        q = q.filter(TestCase.owner_id == user.id)
    return q.first()


def _resolve_project_for_case(db: Session, project_id: int, user: User) -> Project:
    p = db.query(Project).filter(Project.id == project_id).first()
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目空间不存在")
    if not can_view_all_cases(user) and p.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权在该项目空间下创建用例")
    return p


def _require_project_readable(db: Session, project_id: int, user: User) -> Project:
    p = db.query(Project).filter(Project.id == project_id).first()
    if p is None or not project_readable_by_user(db, user, p):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目空间不存在")
    return p


def _append_revision_snapshot(db: Session, tc: TestCase) -> None:
    db.add(
        TestCaseRevision(
            case_id=tc.id,
            revision_no=tc.revision_no,
            title=tc.title,
            task_text=tc.task_text,
            preconditions=tc.preconditions or "",
            steps_json=tc.steps_json or "[]",
            case_format=getattr(tc, "case_format", None) or "structured",
            case_yaml=getattr(tc, "case_yaml", None) or "",
            priority=tc.priority or "P2",
        )
    )


def _validate_test_case_row(tc: TestCase) -> None:
    fmt = (getattr(tc, "case_format", None) or "structured").strip().lower()
    if fmt == "yaml":
        from app.services.case_yaml import validate_case_yaml

        tc.case_yaml = validate_case_yaml(getattr(tc, "case_yaml", "") or "")
        tc.case_format = "yaml"
        return
    tc.case_format = "structured"
    if not (tc.task_text or "").strip() and not parse_steps_json(tc.steps_json):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="执行说明与步骤不能同时为空",
        )


@router.get("", response_model=list[TestCaseOut])
def list_cases(
    project_id: Optional[int] = Query(None, description="按项目空间筛选"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[TestCaseOut]:
    q = case_scope_filter(db, db.query(TestCase), user)
    if project_id is not None:
        proj = db.query(Project).filter(Project.id == project_id).first()
        if proj is None or not project_readable_by_user(db, user, proj):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目空间不存在")
        q = q.filter(TestCase.project_id == project_id)
    rows = q.order_by(desc(TestCase.updated_at)).all()
    return [test_case_to_out(tc) for tc in rows]


@router.post("/convert-format", response_model=CaseFormatConvertOut)
def convert_case_format(
    body: CaseFormatConvertIn,
    user: User = Depends(get_current_user),
) -> CaseFormatConvertOut:
    """编辑弹窗内 structured ↔ yaml 互转（不写库）。"""
    _ = user
    target = body.target_format
    try:
        if target == "yaml":
            case_yaml = structured_to_yaml(
                title=body.title,
                preconditions=body.preconditions,
                steps=body.steps,
                task_text=body.task_text,
            )
            return CaseFormatConvertOut(
                title=body.title,
                preconditions=body.preconditions,
                steps=body.steps,
                task_text=body.task_text,
                case_format="yaml",
                case_yaml=case_yaml,
            )
        parsed = yaml_to_structured(body.case_yaml)
        return CaseFormatConvertOut(
            title=parsed.get("title") or body.title,
            preconditions=parsed.get("preconditions", ""),
            steps=parsed.get("steps") or [],
            task_text=parsed.get("task_text", ""),
            case_format="structured",
            case_yaml="",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post("/generate", response_model=TestCaseGenerateOut)
def generate_case_from_prompt(
    body: TestCaseGenerateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TestCaseGenerateOut:
    """根据用户一句话生成用例草稿（不写库，供前端预览编辑后保存）。"""
    proj = _resolve_project_for_case(db, body.project_id, user)
    log.info(
        "API 用例生成 project_id=%s user_id=%s prompt_len=%s case_format=%s",
        body.project_id,
        user.id,
        len(body.prompt),
        body.case_format,
    )
    try:
        draft = generate_case_draft(
            db,
            project=proj,
            user=user,
            prompt=body.prompt,
            case_format=body.case_format,
        )
    except CaseGeneratorError as e:
        log.warning("API 用例生成失败 project_id=%s: %s", body.project_id, e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except ValueError as e:
        log.warning("API 用例生成格式转换失败 project_id=%s: %s", body.project_id, e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return TestCaseGenerateOut(
        title=draft.title,
        task_text=draft.task_text,
        preconditions=draft.preconditions,
        steps=draft.steps,
        priority=draft.priority,
        case_format=draft.case_format,
        case_yaml=draft.case_yaml,
        generation_meta=CaseGenerateMetaOut(
            model=draft.model,
            similar_case_ids=draft.similar_case_ids or [],
        ),
    )


@router.post("", response_model=TestCaseOut)
def create_case(
    body: TestCaseCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TestCaseOut:
    proj = _resolve_project_for_case(db, body.project_id, user)
    tc = TestCase(
        owner_id=proj.owner_id,
        project_id=proj.id,
        title=body.title.strip(),
        task_text=(body.task_text or "").strip(),
        preconditions=(body.preconditions or "").strip(),
        steps_json=steps_to_json(body.steps),
        case_format=body.case_format,
        case_yaml=(body.case_yaml or "").strip(),
        priority=(body.priority or "P2").strip()[:16],
        revision_no=1,
    )
    _validate_test_case_row(tc)
    db.add(tc)
    db.commit()
    db.refresh(tc)
    _append_revision_snapshot(db, tc)
    upsert_case_kb(db, tc)
    db.commit()
    db.refresh(tc)
    return test_case_to_out(tc)


@router.post("/import", response_model=CaseImportResultOut)
async def import_cases_file(
    project_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CaseImportResultOut:
    proj = _resolve_project_for_case(db, project_id, user)
    raw = await file.read()
    rows_raw, parse_errs = parse_import_file(raw, file.filename or "")
    if parse_errs:
        return CaseImportResultOut(created=0, skipped=0, errors=parse_errs)
    created = 0
    skipped = 0
    errors: list[str] = []
    for i, row in enumerate(rows_raw, start=2):
        body = row_to_create(project_id, row)
        if body is None:
            skipped += 1
            continue
        try:
            tc = TestCase(
                owner_id=proj.owner_id,
                project_id=proj.id,
                title=body.title.strip(),
                task_text=(body.task_text or "").strip(),
                preconditions=(body.preconditions or "").strip(),
                steps_json=steps_to_json(body.steps),
                priority=(body.priority or "P2").strip()[:16],
                revision_no=1,
            )
            db.add(tc)
            db.flush()
            _append_revision_snapshot(db, tc)
            upsert_case_kb(db, tc)
            created += 1
        except Exception as e:
            errors.append(f"第{i}行：{e}")
            skipped += 1
    db.commit()
    return CaseImportResultOut(created=created, skipped=skipped, errors=errors[:50])


@router.get("/runs", response_model=list[TestRunListItemOut])
def list_runs(
    project_id: int = Query(..., description="按项目空间筛选执行记录"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[TestRunListItemOut]:
    """分页列出项目下执行记录（step_log 持久化在库中，可通过 runs/:id 拉取全文）。"""
    proj = _require_project_readable(db, project_id, user)

    q = (
        run_scope_query(db, user)
        .join(TestCase, TestRun.case_id == TestCase.id)
        .filter(TestCase.project_id == project_id)
        .order_by(desc(TestRun.id))
    )
    rows: list[TestRun] = q.offset(offset).limit(limit).all()
    case_ids = {r.case_id for r in rows}
    titles: dict[int, str] = {}
    if case_ids:
        for tc in db.query(TestCase).filter(TestCase.id.in_(case_ids)).all():
            titles[tc.id] = tc.title
    inst_ids = {r.robot_instance_id for r in rows if r.robot_instance_id}
    inst_codes: dict[int, str] = {}
    if inst_ids:
        for ri in db.query(RobotInstance).filter(RobotInstance.id.in_(inst_ids)).all():
            inst_codes[ri.id] = ri.instance_code
    return [
        TestRunListItemOut(
            id=r.id,
            case_id=r.case_id,
            case_title=titles.get(r.case_id, ""),
            project_id=project_id,
            robot_instance_id=r.robot_instance_id,
            robot_instance_code=inst_codes.get(r.robot_instance_id) if r.robot_instance_id else None,
            status=r.status,
            recognition_steps=count_recognition_steps(r.step_log),
            started_at=r.started_at,
            finished_at=r.finished_at,
        )
        for r in rows
    ]


@router.get("/runs/{run_id}", response_model=TestRunOut)
def get_run(
    run_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TestRun:
    r = run_scope_query(db, user).filter(TestRun.id == run_id).first()
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="执行记录不存在")
    return r


@router.get("/runs/{run_id}/report")
def download_run_report(
    run_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FileResponse:
    """下载 Midscene HTML 测试报告（须本次执行已生成 report_path）。"""
    r = run_scope_query(db, user).filter(TestRun.id == run_id).first()
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="执行记录不存在")
    path = resolve_report_file(r.report_path)
    filename = f"midscene-report-run-{run_id}{path.suffix or '.html'}"
    return FileResponse(
        path,
        media_type="text/html; charset=utf-8",
        filename=filename,
    )


@router.post("/runs/{run_id}/cancel", response_model=TestRunOut)
def cancel_run(
    run_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TestRun:
    r = run_scope_query(db, user).filter(TestRun.id == run_id).first()
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="执行记录不存在")
    if r.status not in ("pending", "running"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前任务未在执行中，无法终止",
        )
    signal_cancel(run_id)
    db.refresh(r)
    return r


@router.get("/{case_id}/versions", response_model=list[TestCaseRevisionOut])
def list_case_versions(
    case_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[TestCaseRevisionOut]:
    tc = _get_case_for_read(db, case_id, user)
    if tc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用例不存在")
    revs = (
        db.query(TestCaseRevision)
        .filter(TestCaseRevision.case_id == case_id)
        .order_by(desc(TestCaseRevision.revision_no))
        .all()
    )
    return [revision_to_out(r) for r in revs]


@router.get("/{case_id}", response_model=TestCaseOut)
def get_case(
    case_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TestCaseOut:
    tc = _get_case_for_read(db, case_id, user)
    if tc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用例不存在")
    return test_case_to_out(tc)


@router.patch("/{case_id}", response_model=TestCaseOut)
def update_case(
    case_id: int,
    body: TestCaseUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TestCaseOut:
    tc = _get_case_for_write(db, case_id, user)
    if tc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用例不存在")
    data = body.model_dump(exclude_unset=True)
    if "title" in data and data["title"] is not None:
        tc.title = data["title"].strip()
    if "task_text" in data and data["task_text"] is not None:
        tc.task_text = data["task_text"].strip()
    if "preconditions" in data and data["preconditions"] is not None:
        tc.preconditions = data["preconditions"].strip()
    if "steps" in data and data["steps"] is not None:
        tc.steps_json = steps_to_json([CaseStepJson.model_validate(s) for s in data["steps"]])
    if "priority" in data and data["priority"] is not None:
        tc.priority = data["priority"].strip()[:16]
    if "case_format" in data and data["case_format"] is not None:
        tc.case_format = data["case_format"]
    if "case_yaml" in data and data["case_yaml"] is not None:
        tc.case_yaml = data["case_yaml"].strip()

    _validate_test_case_row(tc)

    tc.revision_no = (tc.revision_no or 1) + 1
    tc.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(tc)
    _append_revision_snapshot(db, tc)
    upsert_case_kb(db, tc)
    db.commit()
    db.refresh(tc)
    return test_case_to_out(tc)


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(
    case_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    tc = _get_case_for_write(db, case_id, user)
    if tc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用例不存在")
    db.delete(tc)
    db.commit()


@router.post("/{case_id}/run", response_model=TestRunOut)
async def run_case(
    case_id: int,
    body: RunCaseBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TestRun:
    tc = _get_case_for_read(db, case_id, user)
    if tc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用例不存在")

    inst = db.query(RobotInstance).filter(RobotInstance.id == body.robot_instance_id).first()
    if inst is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="机器人实例不存在")
    if not can_use_robot_instance(db, user, inst):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权使用该公司下的该机器人实例，或实例不可用",
        )

    busy = find_active_run_for_instance(db, inst.id)
    if busy is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=busy_run_detail_message(busy),
        )

    from app.services.device_platform import resolve_execution_platform

    platform = resolve_execution_platform(
        run_device_platform=body.device_platform,
        instance_device_platform=getattr(inst, "device_platform", None),
        test_agent_backend=getattr(inst, "test_agent_backend", None),
    )

    device_id = (body.device_id or "").strip() or None

    run = TestRun(
        case_id=tc.id,
        owner_id=tc.owner_id,
        robot_instance_id=inst.id,
        device_platform=platform,
        device_id=device_id,
        status="pending",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    prepare_cancel_slot(run.id)
    log.info(
        "API 提交执行 run_id=%s case_id=%s robot_instance_id=%s platform=%s device_id=%s",
        run.id,
        case_id,
        body.robot_instance_id,
        platform,
        device_id or "(默认)",
    )
    asyncio.get_running_loop().run_in_executor(_executor, _run_in_thread, run.id)
    return run
