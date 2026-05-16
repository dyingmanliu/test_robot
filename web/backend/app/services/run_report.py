"""测试执行报告路径校验与文件解析（Midscene HTML 报告）。"""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, status

# .../web/backend/app/services/run_report.py -> parents[4] 为仓库根目录
_REPO_ROOT = Path(__file__).resolve().parents[4]
_MIDSCENE_ROOT = _REPO_ROOT / "midscene_agent"
_MIDSCENE_RUN_ROOT = _MIDSCENE_ROOT / "midscene_run"

# 允许提供下载的报告必须位于这些目录之下（防路径穿越）
_ALLOWED_ROOTS: tuple[Path, ...] = (
    _MIDSCENE_RUN_ROOT.resolve(),
    _MIDSCENE_ROOT.resolve(),
    _REPO_ROOT.resolve(),
)


def normalize_report_path(raw: str | None) -> str | None:
    """将 CLI 返回的报告路径规范化为绝对路径字符串；无法解析时返回 None。"""
    if not raw or not str(raw).strip():
        return None
    p = Path(str(raw).strip()).expanduser()
    if not p.is_absolute():
        p = (_MIDSCENE_ROOT / p).resolve()
    else:
        p = p.resolve()
    return str(p)


def resolve_report_file(stored_path: str | None) -> Path:
    """校验并返回可下载的报告文件路径。"""
    if not stored_path or not str(stored_path).strip():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="本次执行未生成测试报告",
        )
    path = Path(str(stored_path).strip()).expanduser()
    if not path.is_absolute():
        path = (_MIDSCENE_ROOT / path).resolve()
    else:
        path = path.resolve()

    allowed = False
    for root in _ALLOWED_ROOTS:
        try:
            path.relative_to(root)
            allowed = True
            break
        except ValueError:
            continue
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="报告路径不在允许访问的目录内",
        )
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="报告文件不存在或已被清理",
        )
    return path
