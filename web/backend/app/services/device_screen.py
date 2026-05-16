"""通过 ADB / HDC 抓取当前连接设备的屏幕，供 Web 投屏轮询。"""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image

_REPO_ROOT = Path(__file__).resolve().parents[4]


@dataclass
class DeviceScreenFrame:
    image_base64: str
    width: int
    height: int
    backend: str


def _resolve_hdc_executable(hdc_home: str | None = None) -> str:
    raw = (hdc_home or os.getenv("HDC_HOME") or "").strip()
    if not raw:
        found = shutil.which("hdc")
        return found or "hdc"
    if raw.endswith("/hdc") or raw.endswith("\\hdc"):
        return raw
    return f"{raw.rstrip('/')}/hdc"


def _hdc_prefix(device_id: str | None, hdc_home: str | None) -> list[str]:
    bin_path = _resolve_hdc_executable(hdc_home)
    cmd = [bin_path]
    if device_id:
        cmd.extend(["-t", device_id])
    return cmd


def _run_hdc(args: list[str], *, device_id: str | None, hdc_home: str | None, timeout: int = 25) -> None:
    cmd = _hdc_prefix(device_id, hdc_home) + args
    env = {**os.environ}
    if hdc_home:
        env["HDC_HOME"] = hdc_home
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(err or f"hdc {' '.join(args)} 失败 (code {result.returncode})")


def capture_harmony_screen(
    *,
    device_id: str | None = None,
    hdc_home: str | None = None,
) -> DeviceScreenFrame:
    load_dotenv(_REPO_ROOT / ".env")
    dev = device_id or os.getenv("HDC_DEVICE_ID") or None
    home = hdc_home or os.getenv("HDC_HOME") or None
    remote = f"/data/local/tmp/tcm_screen_{uuid.uuid4().hex[:12]}.jpeg"
    local = os.path.join(tempfile.gettempdir(), f"tcm_screen_{uuid.uuid4().hex[:12]}.jpeg")
    try:
        _run_hdc(["shell", "snapshot_display", "-f", remote], device_id=dev, hdc_home=home)
        _run_hdc(["file", "recv", remote, local], device_id=dev, hdc_home=home)
        if not os.path.isfile(local):
            raise RuntimeError("HDC 截屏文件未拉取到本地")
        with Image.open(local) as img:
            width, height = img.size
            buf = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)
            img.save(buf, format="PNG")
            buf.seek(0)
            b64 = base64.b64encode(buf.read()).decode("ascii")
        return DeviceScreenFrame(image_base64=b64, width=width, height=height, backend="midscene")
    finally:
        try:
            _run_hdc(["shell", "rm", "-f", remote], device_id=dev, hdc_home=home, timeout=10)
        except Exception:
            pass
        if os.path.isfile(local):
            try:
                os.remove(local)
            except OSError:
                pass


def capture_android_screen(*, device_id: str | None = None) -> DeviceScreenFrame:
    load_dotenv(_REPO_ROOT / ".env")
    os.chdir(_REPO_ROOT)
    from autoglm_phone_agent.device.adb_bridge import AdbBridge

    dev = device_id or os.getenv("ADB_DEVICE_ID") or None
    shot = AdbBridge(device_id=dev).get_screenshot()
    if not shot.base64_data:
        raise RuntimeError("ADB 截屏为空")
    return DeviceScreenFrame(
        image_base64=shot.base64_data,
        width=shot.width,
        height=shot.height,
        backend="autoglm",
    )


def capture_device_screen(backend: str) -> DeviceScreenFrame:
    b = (backend or "autoglm").strip().lower()
    if b == "midscene":
        return capture_harmony_screen()
    return capture_android_screen()
