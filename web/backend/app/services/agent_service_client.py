"""HTTP 客户端：web backend → agent_service。"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Iterator

import httpx

log = logging.getLogger("app.agent_service_client")

AGENT_SERVICE_URL = os.getenv("AGENT_SERVICE_URL", "http://127.0.0.1:8100")

SHORT_TIMEOUT = httpx.Timeout(120.0, connect=5.0)
SUBMIT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class AgentServiceError(Exception):
    """agent_service 不可达或返回错误。"""


def _base() -> str:
    return AGENT_SERVICE_URL.rstrip("/")


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise AgentServiceError(f"agent_service HTTP {resp.status_code}: {detail}")


# ── 同步短任务 ────────────────────────────────────────────


def generate_case_draft(
    project: dict[str, Any],
    prompt: str,
    kb_snippets: list[str] | None = None,
    *,
    project_id: int | None = None,
    owner_scope_ids: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "project": project,
        "prompt": prompt,
        "kb_snippets": kb_snippets,
    }
    if project_id is not None:
        payload["project_id"] = project_id
    if owner_scope_ids:
        payload["owner_scope_ids"] = owner_scope_ids
    with httpx.Client(timeout=SHORT_TIMEOUT) as client:
        resp = client.post(
            f"{_base()}/api/agent/analysis/generate-case-draft",
            json=payload,
        )
        _raise_for_status(resp)
        return resp.json()


def get_case_gen_config() -> dict[str, Any]:
    with httpx.Client(timeout=SHORT_TIMEOUT) as client:
        resp = client.get(f"{_base()}/api/agent/config/case-generation")
        _raise_for_status(resp)
        return resp.json()


def sync_giic_tree(tree_json: dict[str, Any]) -> dict[str, Any]:
    with httpx.Client(timeout=SHORT_TIMEOUT) as client:
        resp = client.post(f"{_base()}/api/agent/tree/sync-giic", json={"tree_json": tree_json})
        _raise_for_status(resp)
        return resp.json()


def build_function_tree(app_name: str, features: list[dict[str, Any]]) -> dict[str, Any]:
    with httpx.Client(timeout=SHORT_TIMEOUT) as client:
        resp = client.post(
            f"{_base()}/api/agent/tree/build-function-tree",
            json={"app_name": app_name, "features": features},
        )
        _raise_for_status(resp)
        return resp.json()


# ── 长任务：提交 ──────────────────────────────────────────


def submit_func_agent_dispatch(dispatch: dict[str, Any]) -> str:
    with httpx.Client(timeout=SUBMIT_TIMEOUT) as client:
        resp = client.post(f"{_base()}/api/agent/func-agent/dispatch", json=dispatch)
        _raise_for_status(resp)
        return resp.json()["task_id"]


def submit_explore_run(params: dict[str, Any]) -> str:
    with httpx.Client(timeout=SUBMIT_TIMEOUT) as client:
        resp = client.post(f"{_base()}/api/agent/explore/run", json=params)
        _raise_for_status(resp)
        return resp.json()["task_id"]


def submit_midscene_task(dispatch: dict[str, Any]) -> str:
    with httpx.Client(timeout=SUBMIT_TIMEOUT) as client:
        resp = client.post(f"{_base()}/api/agent/midscene/task", json={"dispatch": dispatch})
        _raise_for_status(resp)
        return resp.json()["task_id"]


# ── 长任务：SSE 推流（同步迭代器） ─────────────────────────


def _parse_sse_lines(raw: str) -> Iterator[tuple[str, dict[str, Any]]]:
    """解析 SSE 文本块，yield (event_name, data_dict)。"""
    event = ""
    for line in raw.strip().splitlines():
        if line.startswith("event: "):
            event = line[7:].strip()
        elif line.startswith("data: "):
            try:
                data = json.loads(line[6:])
            except json.JSONDecodeError:
                data = {"raw": line[6:]}
            yield event, data


def stream_func_agent_events(task_id: str) -> Iterator[tuple[str, dict[str, Any]]]:
    return _stream_events(f"{_base()}/api/agent/func-agent/dispatch/{task_id}/stream")


def stream_explore_events(task_id: str) -> Iterator[tuple[str, dict[str, Any]]]:
    return _stream_events(f"{_base()}/api/agent/explore/run/{task_id}/stream")


def stream_midscene_events(task_id: str) -> Iterator[tuple[str, dict[str, Any]]]:
    return _stream_events(f"{_base()}/api/agent/midscene/task/{task_id}/stream")


def _stream_events(url: str) -> Iterator[tuple[str, dict[str, Any]]]:
    """同步阻塞式 SSE 流读取，逐事件 yield。"""
    with httpx.Client(timeout=httpx.Timeout(connect=5.0, read=None, write=30.0, pool=5.0)) as client:
        with client.stream("GET", url) as resp:
            _raise_for_status(resp)
            buffer = ""
            for chunk in resp.iter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    block, buffer = buffer.split("\n\n", 1)
                    yield from _parse_sse_lines(block)


# ── 长任务：取消 ──────────────────────────────────────────


def cancel_task(task_type: str, task_id: str) -> None:
    url_map = {
        "func-agent": f"/api/agent/func-agent/dispatch/{task_id}",
        "explore": f"/api/agent/explore/run/{task_id}",
        "midscene": f"/api/agent/midscene/task/{task_id}",
    }
    url = url_map.get(task_type)
    if url is None:
        return
    with httpx.Client(timeout=SUBMIT_TIMEOUT) as client:
        resp = client.delete(f"{_base()}{url}")
        _raise_for_status(resp)
