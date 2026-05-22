"""项目功能点分析：取消槽与线程入口（执行逻辑见 feature_analysis_bridge）。"""

from __future__ import annotations

import threading

from sqlalchemy.orm import Session

_feature_cancel_events: dict[int, threading.Event] = {}


def get_feature_cancel_event(run_id: int) -> threading.Event:
    return _feature_cancel_events.setdefault(run_id, threading.Event())


def clear_feature_cancel_slot(run_id: int) -> None:
    _feature_cancel_events.pop(run_id, None)


def prepare_feature_cancel_slot(run_id: int) -> None:
    if run_id not in _feature_cancel_events:
        _feature_cancel_events[run_id] = threading.Event()


def signal_feature_cancel(run_id: int) -> bool:
    ev = _feature_cancel_events.get(run_id)
    if ev is None:
        ev = threading.Event()
        ev.set()
        _feature_cancel_events[run_id] = ev
        return True
    ev.set()
    return True


def execute_feature_analysis_run(db: Session, run_id: int) -> None:
    from app.services.feature_analysis_bridge import execute_feature_analysis_run as _run

    _run(db, run_id)
