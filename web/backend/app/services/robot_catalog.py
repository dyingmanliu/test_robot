"""商城 catalog_robot_id 常量（与 marketplace_catalog 对齐）。"""

from __future__ import annotations

CATALOG_TEST_ANALYSIS = "test_analysis"


def is_analysis_catalog(catalog_robot_id: str | None) -> bool:
    return (catalog_robot_id or "").strip() == CATALOG_TEST_ANALYSIS


def is_execution_catalog(catalog_robot_id: str | None) -> bool:
    return not is_analysis_catalog(catalog_robot_id)
