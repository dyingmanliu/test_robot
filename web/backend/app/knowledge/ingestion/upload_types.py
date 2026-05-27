"""知识库上传文件类型与大小限制。"""
from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

# 与 Dify 知识库常见格式对齐（JSON 为平台扩展）
ALLOWED_UPLOAD_SUFFIXES = frozenset({
    ".txt",
    ".md",
    ".markdown",
    ".mdx",
    ".pdf",
    ".html",
    ".htm",
    ".xlsx",
    ".xls",
    ".docx",
    ".csv",
    ".json",
})

SUPPORTED_UPLOAD_HINT = (
    "已支持 TXT、MARKDOWN、MDX、PDF、HTML、XLSX、XLS、DOCX、CSV、MD、HTM、JSON，"
    "每个文件不超过 50MB。"
)

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def validate_upload_path(path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型「{suffix or '未知'}」，请上传 {SUPPORTED_UPLOAD_HINT}",
        )
    size = path.stat().st_size
    if size > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大（{size // (1024 * 1024)}MB），单文件上限 50MB",
        )
