"""通过 ADB / HDC 抓取当前连接设备的屏幕，供 Web 投屏轮询。"""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image

_REPO_ROOT = Path(__file__).resolve().parents[4]

# Web 投屏用缩略图最大宽度；原图 Base64 常 >2MB，浏览器 data: URL 无法渲染会显示黑屏
_MIRROR_MAX_WIDTH = max(240, int(os.getenv("DEVICE_SCREEN_MAX_WIDTH", "540")))


@dataclass
class DeviceScreenFrame:
    image_base64: str
    width: int
    height: int
    backend: str
    mime_type: str = "image/jpeg"


def _prepare_mirror_image(img: Image.Image) -> tuple[str, int, int]:
    """缩小并 JPEG 压缩，供前端轮询投屏（避免超大 data URL 黑屏）。"""
    work = img.convert("RGB") if img.mode not in ("RGB", "L") else img
    w, h = work.size
    if w > _MIRROR_MAX_WIDTH:
        ratio = _MIRROR_MAX_WIDTH / w
        work = work.resize((int(w * ratio), max(1, int(h * ratio))), Image.Resampling.LANCZOS)
    buf = BytesIO()
    work.save(buf, format="JPEG", quality=82, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii"), work.width, work.height


def _frame_from_pil(img: Image.Image, *, backend: str) -> DeviceScreenFrame:
    b64, width, height = _prepare_mirror_image(img)
    return DeviceScreenFrame(
        image_base64=b64,
        width=width,
        height=height,
        backend=backend,
        mime_type="image/jpeg",
    )


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
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
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
            return _frame_from_pil(img, backend="harmonyos")
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
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    os.chdir(_REPO_ROOT)
    from autoglm_phone_tech.device.adb_bridge import AdbBridge

    dev = device_id or os.getenv("ADB_DEVICE_ID") or None
    shot = AdbBridge(device_id=dev).get_screenshot()
    if not shot.base64_data:
        raise RuntimeError("ADB 截屏为空")
    with Image.open(BytesIO(base64.b64decode(shot.base64_data))) as img:
        return _frame_from_pil(img, backend="android")


def capture_device_screen(platform: str, *, device_id: str | None = None) -> DeviceScreenFrame:
    p = (platform or "android").strip().lower()
    if p in ("harmonyos", "harmony", "hmos", "ohos"):
        return capture_harmony_screen(device_id=device_id)
    return capture_android_screen(device_id=device_id)
