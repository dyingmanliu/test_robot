"""内存任务注册表：创建、查询、取消、清理长任务。"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable

from agent_service.service.sse import SSEEvent

log = logging.getLogger("agent_service.task_manager")


class TaskStatus(str, Enum):
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class TaskRecord:
    task_id: str
    status: TaskStatus = TaskStatus.RUNNING
    queue: asyncio.Queue[SSEEvent | None] = field(default_factory=asyncio.Queue)
    cancel_event: threading.Event = field(default_factory=threading.Event)
    created_at: datetime = field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None


class TaskManager:
    def __init__(self) -> None:
        self._tasks: dict[str, TaskRecord] = {}
        self._lock = threading.Lock()

    def create_task(self) -> TaskRecord:
        task_id = uuid.uuid4().hex
        record = TaskRecord(task_id=task_id)
        with self._lock:
            self._tasks[task_id] = record
        log.info("任务创建 task_id=%s", task_id)
        return record

    def get_task(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            return self._tasks.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        record = self.get_task(task_id)
        if record is None or record.status != TaskStatus.RUNNING:
            return False
        record.cancel_event.set()
        log.info("取消请求 task_id=%s", task_id)
        return True

    def cleanup_expired(self, ttl_seconds: int = 3600) -> int:
        cutoff = datetime.utcnow() - timedelta(seconds=ttl_seconds)
        removed = 0
        with self._lock:
            expired = [
                tid
                for tid, rec in self._tasks.items()
                if rec.finished_at is not None and rec.finished_at < cutoff
            ]
            for tid in expired:
                del self._tasks[tid]
                removed += 1
        if removed:
            log.info("清理过期任务 count=%d", removed)
        return removed

    @property
    def active_count(self) -> int:
        with self._lock:
            return sum(1 for r in self._tasks.values() if r.status == TaskStatus.RUNNING)

    def run_background(
        self,
        record: TaskRecord,
        target: Callable[[TaskRecord], None],
    ) -> None:
        """在后台线程中执行 target，捕获异常并标记任务状态。"""
        def _wrapper() -> None:
            try:
                target(record)
            except Exception as exc:
                log.exception("任务异常 task_id=%s", record.task_id)
                record.status = TaskStatus.ERROR
                try:
                    record.queue.put_nowait(SSEEvent(event="error", data={"detail": str(exc)}))
                except Exception:
                    pass
            finally:
                record.finished_at = datetime.utcnow()
                try:
                    record.queue.put_nowait(None)
                except Exception:
                    pass

        t = threading.Thread(target=_wrapper, daemon=True, name=f"agent-task-{record.task_id[:8]}")
        t.start()


# 全局单例
task_manager = TaskManager()
