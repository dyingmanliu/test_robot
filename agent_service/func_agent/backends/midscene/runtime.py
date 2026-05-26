from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from dotenv import load_dotenv


def _resolve_repo_root() -> Path:
    cur = Path(__file__).resolve()
    for parent in cur.parents:
        if (parent / "web" / "backend").is_dir() and (parent / "midscene_tech").is_dir():
            return parent
    return cur.parents[4]


_REPO_ROOT = _resolve_repo_root()


def _find_latest_midscene_report(
    *,
    since_ts: float,
    device_platform: str | None,
) -> str | None:
    """与 web.backend.app.services.run_report.find_latest_midscene_report 逻辑一致（避免 agent 依赖 web）。"""
    report_dir = _REPO_ROOT / "midscene_tech" / "midscene_run" / "report"
    if not report_dir.is_dir():
        return None
    cutoff = since_ts - 2.0
    plat = (device_platform or "").strip().lower()
    prefix: str | None = None
    if plat in ("harmonyos", "harmony", "hmos", "ohos"):
        prefix = "harmony-"
    elif plat == "android":
        prefix = "android-"
    best_mtime = 0.0
    best_path: Path | None = None
    for path in report_dir.glob("*.html"):
        if prefix and not path.name.startswith(prefix):
            continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime < cutoff:
            continue
        if mtime > best_mtime:
            best_mtime = mtime
            best_path = path
    return str(best_path.resolve()) if best_path else None


def _resolve_report_file(
    report_file: str | None,
    *,
    proc_started_at: float,
    device_platform: str,
) -> str | None:
    if report_file and str(report_file).strip():
        return str(report_file).strip()
    return _find_latest_midscene_report(
        since_ts=proc_started_at,
        device_platform=device_platform,
    )


def _build_midscene_cli_cmd(mid_root: Path, cli_rel: Path) -> list[str]:
    node = shutil.which("node") or "node"
    cli = str(cli_rel)
    loader = mid_root / "node_modules" / "tsx" / "dist" / "loader.mjs"
    if loader.is_file():
        return [node, f"--import={loader}", cli, "--web-dispatch"]
    local_tsx = mid_root / "node_modules" / ".bin" / "tsx"
    if local_tsx.is_file():
        return [str(local_tsx), cli, "--web-dispatch"]
    tsx_which = shutil.which("tsx")
    if tsx_which:
        return [tsx_which, str(mid_root / cli_rel), "--web-dispatch"]
    npx = os.getenv("TCM_NPX_BIN", "npx")
    return [npx, "--yes", "tsx", cli, "--web-dispatch"]


def _append_no_proxy_for_midscene_model(env: dict[str, str]) -> None:
    """
    DashScope 在一些本地代理环境下会出现 CONNECT 403。
    当 Midscene 走 DashScope 网关时，自动把目标 host 加入 no_proxy/NO_PROXY，
    避免子进程请求被本地代理错误拦截。
    """
    base_url = (env.get("MIDSCENE_MODEL_BASE_URL") or "").strip()
    if not base_url:
        return
    host = (urlparse(base_url).hostname or "").strip().lower()
    if not host:
        return
    if "dashscope.aliyuncs.com" not in host:
        return

    for key in ("NO_PROXY", "no_proxy"):
        current = env.get(key, "")
        parts = [p.strip() for p in current.split(",") if p.strip()]
        lowered = {p.lower() for p in parts}
        if host not in lowered:
            parts.append(host)
            env[key] = ",".join(parts)


def run_midscene_task(
    dispatch: dict[str, Any],
    *,
    on_machine_line: Callable[[dict[str, Any]], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
    log_model_usage: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[bool, str, str | None]:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    mid_root = _REPO_ROOT / "midscene_tech"
    cli_rel = Path("src/cli.ts")
    if not (mid_root / cli_rel).is_file():
        raise RuntimeError(f"未找到 Midscene CLI：{mid_root / cli_rel}")

    cmd = _build_midscene_cli_cmd(mid_root, cli_rel)
    env = {**os.environ}
    env.setdefault("FORCE_COLOR", "0")
    platform = str(dispatch.get("device_platform") or "harmonyos").strip().lower()
    env["MIDSCENE_DEVICE_PLATFORM"] = platform
    dispatch_device_id = (str(dispatch.get("device_id") or "")).strip()
    if dispatch_device_id:
        if platform in ("harmonyos", "harmony", "hmos", "ohos"):
            env["HDC_DEVICE_ID"] = dispatch_device_id
        else:
            env["ADB_DEVICE_ID"] = dispatch_device_id
    agent_backend = str(dispatch.get("agent_backend") or "midscene").strip().lower()
    if agent_backend == "autoglm":
        env["MIDSCENE_AGENT_BACKEND"] = "autoglm"
    env.setdefault("MIDSCENE_REPLANNING_CYCLE_LIMIT", "100")
    env.setdefault("MIDSCENE_STEP_TIMEOUT_SEC", "180")
    _append_no_proxy_for_midscene_model(env)

    proc = subprocess.Popen(
        cmd,
        cwd=str(mid_root),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )
    assert proc.stdin is not None and proc.stdout is not None
    stdin_payload = json.dumps(dispatch, ensure_ascii=False, default=str) + "\n"

    def write_stdin() -> None:
        try:
            proc.stdin.write(stdin_payload)
            proc.stdin.close()
        except BrokenPipeError:
            pass

    threading.Thread(target=write_stdin, daemon=True).start()
    line_q: queue.Queue[str | None] = queue.Queue()

    def reader() -> None:
        try:
            for raw in iter(proc.stdout.readline, ""):
                line_q.put(raw)
        finally:
            line_q.put(None)

    threading.Thread(target=reader, daemon=True).start()
    proc_started_at = time.time()
    final_ok: bool | None = None
    final_message = ""
    final_report_file: str | None = None
    non_json_lines: list[str] = []

    def drain_queue() -> None:
        while True:
            try:
                raw = line_q.get_nowait()
            except queue.Empty:
                break
            if raw is None:
                break
            process_line(raw)

    def process_line(raw: str) -> None:
        nonlocal final_ok, final_message, final_report_file
        line = raw.strip()
        if not line:
            return
        try:
            obj: dict[str, Any] = json.loads(line)
        except json.JSONDecodeError:
            non_json_lines.append(line)
            return
        if obj.get("kind") == "model_usage" and log_model_usage:
            log_model_usage(obj)
        if on_machine_line:
            on_machine_line(obj)
        if obj.get("kind") == "done":
            final_ok = bool(obj.get("ok"))
            final_message = str(obj.get("message") or "")
            rf = obj.get("reportFile")
            if rf is not None and str(rf).strip():
                final_report_file = str(rf).strip()

    while True:
        if should_cancel and should_cancel():
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            drain_queue()
            report = _resolve_report_file(
                final_report_file,
                proc_started_at=proc_started_at,
                device_platform=platform,
            )
            return False, "执行已取消", report
        try:
            raw = line_q.get(timeout=0.35)
        except queue.Empty:
            if proc.poll() is not None:
                drain_queue()
                break
            continue
        if raw is None:
            break
        process_line(raw)

    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
    drain_queue()

    report = _resolve_report_file(
        final_report_file,
        proc_started_at=proc_started_at,
        device_platform=platform,
    )

    if final_ok is not None:
        return final_ok, final_message, report
    code = proc.returncode if proc.returncode is not None else -1
    detail = ""
    for candidate in reversed(non_json_lines):
        if candidate.startswith("Error:"):
            detail = candidate.removeprefix("Error:").strip()
            break
    if not detail and non_json_lines:
        detail = non_json_lines[-1][:500]
    if detail:
        return False, detail, report
    return False, f"Midscene 子进程异常结束（exit {code}），未收到结果行", report
