"""MAI-UI 识图：服务状态、截图 Grounding。"""

from __future__ import annotations

import json
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.deps import get_current_user
from app.models import User
from app.services import mai_ui_service

router = APIRouter(prefix="/mai-ui", tags=["mai-ui"])

_MAX_IMAGE_BYTES = 12 * 1024 * 1024
_ALLOWED_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}


@router.get("/status")
def mai_ui_status(_user: User = Depends(get_current_user)) -> dict:
    """检查本地 MAI-UI 推理服务（vllm-mlx / Ollama 等）是否可达。"""
    try:
        return mai_ui_service.get_mai_ui_status()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"MAI-UI 状态检查失败：{e}",
        ) from e


@router.post("/ground")
async def mai_ui_ground(
    file: Annotated[UploadFile, File(description="APP 截图 PNG/JPEG/WebP")],
    query: Annotated[str, Form(description="要定位的控件描述")] = "",
    queries: Annotated[Optional[str], Form(description="多条描述，JSON 数组或换行分隔")] = None,
    _user: User = Depends(get_current_user),
) -> dict:
    """上传截图并按自然语言描述定位 UI 元素坐标。"""
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type and content_type not in _ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的图片类型：{content_type}")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="图片为空")
    if len(raw) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="图片过大（最大 12MB）")

    instructions = _parse_queries(query, queries)
    if not instructions:
        raise HTTPException(status_code=400, detail="请填写定位描述 query 或 queries")

    try:
        return mai_ui_service.run_grounding(raw, instructions)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"MAI-UI 推理失败：{e}") from e


@router.post("/detect-menus")
async def mai_ui_detect_menus(
    file: Annotated[UploadFile, File(description="APP 截图 PNG/JPEG/WebP")],
    _user: User = Depends(get_current_user),
) -> dict:
    """上传截图，一次性识别当前页全部导航菜单（含顶部、底部等）。"""
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type and content_type not in _ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的图片类型：{content_type}")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="图片为空")
    if len(raw) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="图片过大（最大 12MB）")

    try:
        result = mai_ui_service.run_menu_detect(raw)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"MAI-UI 菜单识别失败：{e}") from e

    if not result.get("ok"):
        raise HTTPException(
            status_code=502,
            detail=result.get("error") or "菜单识别失败",
        )

    return result


def _parse_queries(query: str, queries: Optional[str]) -> List[str]:
    out: List[str] = []
    if queries and queries.strip():
        raw = queries.strip()
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    out.extend(str(x).strip() for x in parsed if str(x).strip())
            except json.JSONDecodeError:
                pass
        if not out:
            out.extend(line.strip() for line in raw.splitlines() if line.strip())
    q = (query or "").strip()
    if q and q not in out:
        out.insert(0, q)
    elif q and not out:
        out.append(q)
    return out
