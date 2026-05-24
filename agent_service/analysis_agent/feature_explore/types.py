"""功能点遍历：dispatch 载荷与执行结果（与 midscene explore JSONL 对齐）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ExploreDispatch:
    """写入 Midscene CLI stdin 的 explore 任务。"""

    device_platform: str
    device_id: str
    app_name: str
    bundle_id: str
    max_screens: int = 30
    max_depth: int = 4
    traverse_mode: str = "hybrid"
    bfs_max_depth: int = 1
    fair_share_per_root: int = 0
    run_id: int | None = None
    robot_instance_id: int | None = None

    def to_midscene_payload(self) -> dict[str, Any]:
        return {
            "version": 1,
            "execution_mode": "explore",
            "run_id": self.run_id,
            "robot_instance_id": self.robot_instance_id,
            "agent_backend": "midscene",
            "device_platform": self.device_platform,
            "device_id": self.device_id or "",
            "app_name": self.app_name,
            "bundle_id": self.bundle_id,
            "max_screens": self.max_screens,
            "max_depth": self.max_depth,
            "traverse_mode": self.traverse_mode,
            "bfs_max_depth": self.bfs_max_depth,
            "fair_share_per_root": self.fair_share_per_root,
        }


@dataclass
class ExploreRunResult:
    ok: bool
    message: str
    tree: dict[str, Any] | None = None
    report_file: str | None = None


MachineLineCallback = Callable[[dict[str, Any]], None]
CancelCheck = Callable[[], bool]
