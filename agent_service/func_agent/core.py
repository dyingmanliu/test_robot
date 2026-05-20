from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class FuncAgentDispatch:
    backend: str
    device_platform: str
    device_id: str | None
    payload: dict[str, Any]
