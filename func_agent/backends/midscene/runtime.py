from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[3]


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


def run_midscene_task(
    dispatch: dict[str, Any],
    *,
    on_machine_line: Callable[[dict[str, Any]], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
    log_model_usage: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[bool, str, str | None]:
    load_dotenv(_REPO_ROOT / ".env")
    mid_root = _REPO_ROOT / "midscene_agent"
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
    final_ok: bool | None = None
    final_message = ""
    final_report_file: str | None = None
    non_json_lines: list[str] = []

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
            return False, "执行已取消", None
        try:
            raw = line_q.get(timeout=0.35)
        except queue.Empty:
            if proc.poll() is not None:
                while True:
                    try:
                        r = line_q.get_nowait()
                    except queue.Empty:
                        break
                    if r is None:
                        break
                    process_line(r)
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

    if final_ok is not None:
        return final_ok, final_message, final_report_file
    code = proc.returncode if proc.returncode is not None else -1
    detail = ""
    for candidate in reversed(non_json_lines):
        if candidate.startswith("Error:"):
            detail = candidate.removeprefix("Error:").strip()
            break
    if not detail and non_json_lines:
        detail = non_json_lines[-1][:500]
    if detail:
        return False, detail, None
    return False, f"Midscene 子进程异常结束（exit {code}），未收到结果行", None
