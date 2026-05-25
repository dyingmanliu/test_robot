"""SSE 响应辅助工具。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SSEEvent:
    event: str
    data: dict[str, Any] = field(default_factory=dict)

    def format(self) -> str:
        payload = json.dumps(self.data, ensure_ascii=False)
        return f"event: {self.event}\ndata: {payload}\n\n"
