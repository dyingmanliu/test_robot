"""LangChain callback：映射到 agent_service SSE 事件名。"""
from __future__ import annotations

from typing import Any, Callable

from langchain_core.callbacks import BaseCallbackHandler


class SSEProgressCallback(BaseCallbackHandler):
    """将 LLM 生命周期事件转为通用 dict，由 router 映射为 step|line|usage。"""

    def __init__(self, on_event: Callable[[str, dict[str, Any]], None] | None = None) -> None:
        self.on_event = on_event

    def _emit(self, event: str, data: dict[str, Any]) -> None:
        if self.on_event:
            self.on_event(event, data)

    def on_llm_start(self, serialized: dict[str, Any], prompts: list[str], **kwargs: Any) -> None:
        self._emit("line", {"kind": "llm_start", "prompt_count": len(prompts)})

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        self._emit("line", {"kind": "llm_end"})

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        self._emit("error", {"detail": str(error)})
