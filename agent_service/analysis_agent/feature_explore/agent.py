"""功能菜单树遍历：编排 Midscene explore 子进程，聚合功能树结果。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from agent_service.analysis_agent.feature_explore.types import (
    CancelCheck,
    ExploreDispatch,
    ExploreRunResult,
    MachineLineCallback,
)
from agent_service.func_agent.backends.midscene.runtime import run_midscene_task


def _repo_root() -> Path:
    cur = Path(__file__).resolve()
    for parent in cur.parents:
        if (parent / "web" / "backend").is_dir() and (parent / "midscene_tech").is_dir():
            return parent
    return cur.parents[4]


class FeatureExploreAgent:
    """
    测试分析机器人 — 真机功能点 DFS 编排。
    设备操作由 midscene_tech/explore.ts 执行；本类只组 dispatch 与解析事件流。
    """

    def __init__(self, *, repo_root: Path | None = None) -> None:
        self._repo_root = repo_root or _repo_root()

    def run(
        self,
        dispatch: ExploreDispatch,
        *,
        on_machine_line: MachineLineCallback | None = None,
        should_cancel: CancelCheck | None = None,
        log_model_usage: MachineLineCallback | None = None,
    ) -> ExploreRunResult:
        load_dotenv(Path(__file__).resolve().parents[2] / ".env")
        tree_holder: dict[str, Any] = {"tree": None}
        feature_json_holder: dict[str, Any] = {"features": []}

        def handle_line(obj: dict[str, Any]) -> None:
            if obj.get("kind") == "model_usage" and log_model_usage:
                log_model_usage(obj)
            if on_machine_line:
                on_machine_line(obj)
            if obj.get("kind") == "done" and isinstance(obj.get("tree"), dict):
                tree_holder["tree"] = obj["tree"]
            if obj.get("kind") == "explore_feature":
                feat = obj.get("feature")
                if isinstance(feat, dict):
                    feats = feature_json_holder.get("features")
                    if isinstance(feats, list):
                        feats.append(feat)

        try:
            ok, msg, report_file = run_midscene_task(
                dispatch.to_midscene_payload(),
                on_machine_line=handle_line,
                should_cancel=should_cancel,
                log_model_usage=log_model_usage,
            )
        except Exception as exc:
            return ExploreRunResult(ok=False, message=f"功能点分析执行异常: {exc}")

        tree = tree_holder.get("tree")
        if tree is None and feature_json_holder.get("features"):
            tree = {
                "app_name": dispatch.app_name,
                "bundle_id": dispatch.bundle_id,
                "features": feature_json_holder["features"],
                "screens_visited": 0,
            }

        if tree is None:
            tree = self._empty_tree(dispatch)

        return ExploreRunResult(ok=ok, message=msg, tree=tree, report_file=report_file)

    @staticmethod
    def merge_feature_from_line(
        existing_json: str | None,
        obj: dict[str, Any],
    ) -> tuple[str, int]:
        """从 explore_feature 事件增量更新 feature_json 字符串。"""
        try:
            existing = json.loads(existing_json or "{}")
        except json.JSONDecodeError:
            existing = {"features": []}
        feats = existing.get("features")
        if not isinstance(feats, list):
            feats = []
        feat = obj.get("feature")
        if isinstance(feat, dict):
            feats.append(feat)
            existing["features"] = feats
        return json.dumps(existing, ensure_ascii=False), len(feats)

    @staticmethod
    def finalize_tree(
        *,
        tree: dict[str, Any] | None,
        feature_json: str | None,
        app_name: str,
        bundle_id: str,
        started_at: datetime | None,
        screens_visited: int,
    ) -> dict[str, Any]:
        if tree is None and feature_json:
            try:
                tree = json.loads(feature_json)
            except json.JSONDecodeError:
                tree = None
        if tree is None:
            tree = {
                "app_name": app_name,
                "bundle_id": bundle_id,
                "started_at": started_at.isoformat() if started_at else "",
                "finished_at": datetime.utcnow().isoformat(),
                "features": [],
                "screens_visited": screens_visited or 0,
            }
        tree.setdefault("app_name", app_name)
        tree.setdefault("bundle_id", bundle_id)
        tree["finished_at"] = datetime.utcnow().isoformat()
        from agent_service.analysis_agent.feature_explore.tree_build import ensure_giic_tree

        return ensure_giic_tree(tree)

    @staticmethod
    def _empty_tree(dispatch: ExploreDispatch) -> dict[str, Any]:
        return {
            "app_name": dispatch.app_name,
            "bundle_id": dispatch.bundle_id,
            "started_at": datetime.utcnow().isoformat(),
            "finished_at": datetime.utcnow().isoformat(),
            "features": [],
            "screens_visited": 0,
        }
