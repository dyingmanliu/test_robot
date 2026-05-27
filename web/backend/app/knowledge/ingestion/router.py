"""按 doc_type 与文件类型路由解析器。"""
from __future__ import annotations

from app.knowledge.ingestion.parsers import parse_document_content
from app.models import TestCase


def route_and_parse(
    *,
    file_path: str | None,
    structured_json: str,
    doc_type: str,
    case: TestCase | None = None,
    feature_tree_json: str | None = None,
) -> str:
    """统一入口：根据 doc_type / mime 解析为纯文本。"""
    return parse_document_content(
        file_path=file_path,
        structured_json=structured_json,
        doc_type=doc_type,
        case=case,
        feature_tree_json=feature_tree_json,
    )
