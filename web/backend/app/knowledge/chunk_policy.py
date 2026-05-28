"""项目 / 文档级切片参数（页面可配置，缺省读环境变量）。"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

import os

from app.knowledge.config import DEFAULT_CHUNK_POLICY, kb_search_min_score

# 文档级仅覆盖索引切片字段；最低相似度仍由项目 / 环境决定
DOCUMENT_CHUNK_KEYS = (
    "max_chars",
    "overlap",
    "overlap_short",
    "prefix_title",
    "prefix_section",
    "heading_aware",
)


def default_chunk_policy_from_env() -> dict[str, Any]:
    """环境变量默认；项目页配置会覆盖。"""
    def _env_int(name: str, default: int) -> int:
        raw = (os.getenv(name) or "").strip()
        if not raw:
            return default
        try:
            return int(raw)
        except ValueError:
            return default

    return normalize_chunk_policy(
        {
            "max_chars": _env_int("KB_CHUNK_MAX_CHARS", DEFAULT_CHUNK_POLICY["max_chars"]),
            "overlap": _env_int("KB_CHUNK_OVERLAP", DEFAULT_CHUNK_POLICY["overlap"]),
            "overlap_short": _env_int(
                "KB_CHUNK_OVERLAP_SHORT", DEFAULT_CHUNK_POLICY["overlap_short"]
            ),
            "prefix_title": (os.getenv("KB_CHUNK_PREFIX_TITLE") or "1").strip().lower()
            not in ("0", "false", "no"),
            "prefix_section": (os.getenv("KB_CHUNK_PREFIX_SECTION") or "1").strip().lower()
            not in ("0", "false", "no"),
            "heading_aware": (os.getenv("KB_CHUNK_HEADING_AWARE") or "1").strip().lower()
            not in ("0", "false", "no"),
            "search_min_score": (os.getenv("KB_SEARCH_MIN_SCORE") or "").strip() or None,
        }
    )


def _clamp_int(value: Any, *, default: int, lo: int, hi: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def _clamp_bool(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return default


def normalize_chunk_policy(raw: dict | None) -> dict[str, Any]:
    base = dict(DEFAULT_CHUNK_POLICY)
    if not raw:
        return base
    max_chars = _clamp_int(raw.get("max_chars"), default=base["max_chars"], lo=200, hi=4000)
    overlap = _clamp_int(raw.get("overlap"), default=base["overlap"], lo=0, hi=800)
    overlap_short = _clamp_int(
        raw.get("overlap_short"), default=base["overlap_short"], lo=0, hi=400
    )
    if overlap >= max_chars:
        overlap = max(0, max_chars // 5)
    if overlap_short >= max_chars:
        overlap_short = max(0, max_chars // 8)
    out = {
        "max_chars": max_chars,
        "overlap": overlap,
        "overlap_short": overlap_short,
        "prefix_title": _clamp_bool(raw.get("prefix_title"), default=base["prefix_title"]),
        "prefix_section": _clamp_bool(raw.get("prefix_section"), default=base["prefix_section"]),
        "heading_aware": _clamp_bool(raw.get("heading_aware"), default=base["heading_aware"]),
    }
    if "search_min_score" in raw and raw.get("search_min_score") is not None:
        try:
            score = float(raw["search_min_score"])
            out["search_min_score"] = max(0.0, min(1.0, score))
        except (TypeError, ValueError):
            out["search_min_score"] = None
    else:
        out["search_min_score"] = raw.get("search_min_score")
    return out


def normalize_document_chunk_policy(raw: dict | None) -> dict[str, Any]:
    """文档级覆盖：仅保留切片相关字段。"""
    full = normalize_chunk_policy(raw)
    return {k: full[k] for k in DOCUMENT_CHUNK_KEYS}


def has_document_chunk_override(raw_json: str | None) -> bool:
    if not raw_json or not isinstance(raw_json, str):
        return False
    return raw_json.strip() not in ("", "{}")


def _merge_project_chunk_policy(db: Session, project_id: int) -> dict[str, Any]:
    policy = default_chunk_policy_from_env()
    from app.models import ProjectKnowledgeSettings

    row = (
        db.query(ProjectKnowledgeSettings)
        .filter(ProjectKnowledgeSettings.project_id == project_id)
        .first()
    )
    if row is None:
        return policy
    raw_json = row.chunk_policy_json
    if not raw_json or not isinstance(raw_json, str) or not raw_json.strip():
        return policy
    try:
        stored = json.loads(raw_json)
    except json.JSONDecodeError:
        return policy
    if not isinstance(stored, dict):
        return policy
    return normalize_chunk_policy({**policy, **stored})


def resolve_chunk_policy(
    db: Session | None,
    project_id: int | None,
    document_id: int | None = None,
) -> dict[str, Any]:
    """合并 环境 → 项目 → 文档（可选）。"""
    if db is None or project_id is None:
        return default_chunk_policy_from_env()
    policy = _merge_project_chunk_policy(db, project_id)
    if document_id is None:
        return policy
    from app.models import KnowledgeDocument

    doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == document_id).first()
    if doc is None or not has_document_chunk_override(doc.chunk_policy_json):
        return policy
    raw_json = doc.chunk_policy_json
    if not isinstance(raw_json, str):
        return policy
    try:
        stored = json.loads(raw_json)
    except json.JSONDecodeError:
        return policy
    if not isinstance(stored, dict):
        return policy
    return normalize_chunk_policy({**policy, **stored})


def effective_search_min_score(policy: dict[str, Any]) -> float:
    raw = policy.get("search_min_score")
    if raw is not None and raw != "":
        try:
            return max(0.0, min(1.0, float(raw)))
        except (TypeError, ValueError):
            pass
    return kb_search_min_score()
