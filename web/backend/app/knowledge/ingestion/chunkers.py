"""按 doc_type 切片（不依赖 NLTK，避免索引任务因 stopwords 缺失而卡死）。"""
from __future__ import annotations


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


def chunk_text(text: str, *, doc_type: str, max_chars: int = 800) -> list[tuple[str, str]]:
    """返回 (section_path, content) 列表。"""
    t = (text or "").strip()
    if not t:
        return []
    if doc_type in ("case", "ui_element", "page_model"):
        if len(t) <= max_chars:
            return [("", t)]
        nodes = _split_by_size(t, max_chars=max_chars, overlap=80)
        return [(f"part-{i+1}", n) for i, n in enumerate(nodes)]
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
    nodes = _split_by_size(t, max_chars=max_chars, overlap=100)
    return [(f"sec-{i+1}", n) for i, n in enumerate(nodes)]
