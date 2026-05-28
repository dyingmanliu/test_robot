"""按 doc_type 切片（不依赖 NLTK，避免索引任务因 stopwords 缺失而卡死）。"""
from __future__ import annotations

import re
from typing import Any

_HEADING_LINE = re.compile(
    r"^(?:#{1,6}\s+|\d+(?:\.\d+)+\s+|[一二三四五六七八九十]+[、.．]\s*|\(\d+\)\s*)"
)


def _split_by_size(text: str, *, max_chars: int, overlap: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + max_chars, n)
        if end < n:
            break_at = text.rfind("\n\n", start, end)
            if break_at <= start:
                break_at = text.rfind("\n", start, end)
            if break_at <= start:
                break_at = text.rfind("。", start, end)
            if break_at > start:
                end = break_at + 1
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks or [text]


def _chunk_by_headings(text: str, *, max_chars: int, overlap: int) -> list[tuple[str, str]]:
    """按章节标题切分（如 6.3 条件分支），过长章节再定长切。"""
    lines = text.splitlines()
    if not lines:
        return [("", text)]
    sections: list[tuple[str, list[str]]] = []
    current_heading = ""
    buf: list[str] = []
    for ln in lines:
        stripped = ln.strip()
        if stripped and _HEADING_LINE.match(stripped):
            if buf:
                sections.append((current_heading, buf))
            current_heading = stripped[:120]
            buf = [ln]
        else:
            buf.append(ln)
    if buf:
        sections.append((current_heading, buf))
    if len(sections) <= 1 and not sections[0][0]:
        return [(f"sec-{i + 1}", n) for i, n in enumerate(_split_by_size(text, max_chars=max_chars, overlap=overlap))]

    out: list[tuple[str, str]] = []
    for heading, body_lines in sections:
        body = "\n".join(body_lines).strip()
        if not body:
            continue
        if len(body) <= max_chars:
            out.append((heading, body))
            continue
        for i, piece in enumerate(_split_by_size(body, max_chars=max_chars, overlap=overlap)):
            sec = heading if i == 0 else f"{heading} (续{i})"
            out.append((sec, piece))
    return out or [("", text)]


def chunk_text(
    text: str,
    *,
    doc_type: str,
    max_chars: int = 800,
    overlap: int = 100,
    overlap_short: int = 80,
    heading_aware: bool = True,
) -> list[tuple[str, str]]:
    """返回 (section_path, content) 列表。"""
    t = (text or "").strip()
    if not t:
        return []
    short_overlap = overlap_short if overlap_short >= 0 else overlap
    if doc_type in ("case", "ui_element", "page_model"):
        if len(t) <= max_chars:
            return [("", t)]
        nodes = _split_by_size(t, max_chars=max_chars, overlap=short_overlap)
        return [(f"part-{i + 1}", n) for i, n in enumerate(nodes)]
    if doc_type == "feature_tree":
        lines = [ln for ln in t.splitlines() if ln.strip()]
        chunks: list[tuple[str, str]] = []
        buf: list[str] = []
        for ln in lines:
            buf.append(ln)
            if len("\n".join(buf)) >= max_chars:
                chunks.append(("", "\n".join(buf)))
                buf = []
        if buf:
            chunks.append(("", "\n".join(buf)))
        return chunks or [("", t)]
    if heading_aware and doc_type in ("standard", "strategy", "glossary", "other"):
        return _chunk_by_headings(t, max_chars=max_chars, overlap=overlap)
    nodes = _split_by_size(t, max_chars=max_chars, overlap=overlap)
    return [(f"sec-{i + 1}", n) for i, n in enumerate(nodes)]


def build_embed_text(
    *,
    doc_title: str,
    section_path: str,
    content: str,
    policy: dict[str, Any],
) -> str:
    """拼接用于 embedding 的文本（展示仍用原始 content）。"""
    parts: list[str] = []
    if policy.get("prefix_title") and (doc_title or "").strip():
        parts.append(f"【文档】{doc_title.strip()}")
    if policy.get("prefix_section") and (section_path or "").strip():
        parts.append(f"【章节】{section_path.strip()}")
    parts.append((content or "").strip())
    return "\n".join(p for p in parts if p)
