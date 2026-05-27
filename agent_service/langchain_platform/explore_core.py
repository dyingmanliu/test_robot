"""功能点分析核心逻辑（LangGraph 与 FeatureExploreAgent 共用）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from agent_service.analysis_agent.feature_explore.types import (
    CancelCheck,
    ExploreDispatch,
    ExploreRunResult,
    MachineLineCallback,
)
from agent_service.langchain_platform.tools.midscene_dispatch import run_midscene_explore_dispatch


def execute_explore_run(
    dispatch: ExploreDispatch,
    *,
    on_machine_line: MachineLineCallback | None = None,
    should_cancel: CancelCheck | None = None,
    log_model_usage: MachineLineCallback | None = None,
) -> ExploreRunResult:
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
        ok, msg, report_file = run_midscene_explore_dispatch(
            dispatch,
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
        tree = {
            "app_name": dispatch.app_name,
            "bundle_id": dispatch.bundle_id,
            "started_at": datetime.utcnow().isoformat(),
            "finished_at": datetime.utcnow().isoformat(),
            "features": [],
            "screens_visited": 0,
        }

    return ExploreRunResult(ok=ok, message=msg, tree=tree, report_file=report_file)
