"""设备池目录（占位）：对接设备管理服务后可改为 HTTP 拉取。"""

from __future__ import annotations

from typing import Any


def list_device_pools() -> list[dict[str, Any]]:
    return [
        {
            "id": "default-android",
            "name": "默认 Android 设备池",
            "region": "cn-east",
            "description": "通用真机与模拟器混合池；对接 Agent 管理后展示实时容量。",
        },
        {
            "id": "high-availability",
            "name": "高可用池（多机热备）",
            "region": "cn-east",
            "description": "适用于里程碑回归；调度层优先从此池分配闲机。",
        },
        {
            "id": "smoke-small",
            "name": "冒烟专用小池",
            "region": "cn-north",
            "description": "低延时短任务；设备数量较少。",
        },
    ]


def is_known_pool(pool_id: str) -> bool:
    return any(p["id"] == pool_id for p in list_device_pools())
