# SPDX-License-Identifier: Apache-2.0
"""轻量 HTTP 服务：常驻加载 MAI-UI-2B，供 Web 后端（Python 3.9）调用。"""

from __future__ import annotations

import argparse
import base64
import json
import os
import threading
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
from io import BytesIO
from typing import Any

from PIL import Image

from mai_ui_agent.config import load_config
from mai_ui_agent.grounding import MaiUiGroundingAgent
from mai_ui_agent.menu_detect import MaiUiMenuDetectAgent


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class GroundingHandler(BaseHTTPRequestHandler):
    agent: MaiUiGroundingAgent | None = None
    menu_agent: MaiUiMenuDetectAgent | None = None
    request_lock: threading.Lock = threading.Lock()

    def log_message(self, fmt: str, *args) -> None:
        if os.getenv("MAI_UI_VERBOSE", "").strip().lower() in ("1", "true", "yes"):
            super().log_message(fmt, *args)

    def _request_path(self) -> str:
        return urlparse(self.path).path.rstrip("/") or "/"

    def do_GET(self) -> None:
        if self._request_path() in ("", "/health", "/healthz"):
            _json_response(
                self,
                200,
                {
                    "ok": True,
                    "backend": "mlx_vlm",
                    "model_path": self.agent.config.model_path if self.agent else None,
                },
            )
            return
        _json_response(self, 404, {"ok": False, "error": "not found"})

    def _read_json_body(self) -> tuple[dict[str, Any] | None, str | None]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None, "invalid Content-Length"
        try:
            raw = self.rfile.read(length)
            data = json.loads(raw.decode("utf-8"))
            if not isinstance(data, dict):
                return None, "JSON body 应为对象"
            return data, None
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return None, f"invalid JSON: {e}"

    def _decode_image_b64(self, image_b64: str) -> tuple[Image.Image | None, str | None]:
        try:
            image_bytes = base64.b64decode(image_b64, validate=True)
            img = Image.open(BytesIO(image_bytes))
            if img.mode != "RGB":
                img = img.convert("RGB")
            return img, None
        except Exception as e:
            return None, f"图片解码失败: {e}"

    def do_POST(self) -> None:
        path = self._request_path()
        if path == "/detect-menus":
            self._handle_detect_menus()
            return
        if path != "/ground":
            _json_response(self, 404, {"ok": False, "error": "not found"})
            return

        data, err = self._read_json_body()
        if err:
            _json_response(self, 400, {"ok": False, "error": err})
            return

        instructions = data.get("instructions") or []
        if isinstance(instructions, str):
            instructions = [instructions]
        instructions = [str(x).strip() for x in instructions if str(x).strip()]
        if not instructions:
            _json_response(self, 400, {"ok": False, "error": "instructions 不能为空"})
            return

        image_b64 = data.get("image_base64")
        if not image_b64:
            _json_response(self, 400, {"ok": False, "error": "缺少 image_base64"})
            return

        img, img_err = self._decode_image_b64(image_b64)
        if img_err:
            _json_response(self, 400, {"ok": False, "error": img_err})
            return

        if GroundingHandler.agent is None:
            cfg = load_config({"backend": "mlx_vlm"})
            GroundingHandler.agent = MaiUiGroundingAgent(cfg)

        orig_w, orig_h = img.size
        cfg = GroundingHandler.agent.config

        try:
            with GroundingHandler.request_lock:
                results = [
                    GroundingHandler.agent.ground(q, img).to_dict()
                    for q in instructions
                ]
        except Exception as e:
            err = str(e).strip() or type(e).__name__
            if os.getenv("MAI_UI_VERBOSE", "").strip().lower() in ("1", "true", "yes"):
                traceback.print_exc()
            hint = (
                "Mac 16GB 上 Metal 可能因截图过大崩溃；"
                f"可在 .env 降低 MAI_UI_MAX_IMAGE_LONG_EDGE（当前 {cfg.max_image_long_edge}），"
                "并重启 serve_grounding_mlx.sh"
            )
            _json_response(
                self,
                500,
                {"ok": False, "error": f"{err}. {hint}", "results": []},
            )
            return

        _json_response(
            self,
            200,
            {
                "image_width": orig_w,
                "image_height": orig_h,
                "results": results,
            },
        )

    def _handle_detect_menus(self) -> None:
        data, err = self._read_json_body()
        if err:
            _json_response(self, 400, {"ok": False, "error": err})
            return

        image_b64 = data.get("image_base64")
        if not image_b64:
            _json_response(self, 400, {"ok": False, "error": "缺少 image_base64"})
            return

        img, img_err = self._decode_image_b64(image_b64)
        if img_err:
            _json_response(self, 400, {"ok": False, "error": img_err})
            return

        if GroundingHandler.menu_agent is None:
            cfg = load_config({"backend": "mlx_vlm"})
            GroundingHandler.menu_agent = MaiUiMenuDetectAgent(cfg)

        cfg = GroundingHandler.menu_agent.config
        try:
            with GroundingHandler.request_lock:
                result = GroundingHandler.menu_agent.detect(img)
            payload = result.to_dict()
            status = 200 if result.ok else 500
            _json_response(self, status, payload)
        except Exception as e:
            err_msg = str(e).strip() or type(e).__name__
            if os.getenv("MAI_UI_VERBOSE", "").strip().lower() in ("1", "true", "yes"):
                traceback.print_exc()
            hint = (
                "Mac 16GB 上 Metal 可能因截图过大崩溃；"
                f"可在 .env 降低 MAI_UI_MAX_IMAGE_LONG_EDGE（当前 {cfg.max_image_long_edge}），"
                "并重启 serve_grounding_mlx.sh"
            )
            _json_response(
                self,
                500,
                {"ok": False, "error": f"{err_msg}. {hint}", "menus": []},
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MAI-UI mlx_vlm Grounding HTTP 服务")
    parser.add_argument("--host", default=os.getenv("MAI_UI_GROUNDING_HOST", "127.0.0.1"))
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MAI_UI_GROUNDING_PORT", "8101")),
    )
    args = parser.parse_args(argv)

    os.environ.setdefault("MAI_UI_BACKEND", "mlx_vlm")
    cfg = load_config({"backend": "mlx_vlm"})
    print(f"[mai_ui] 预加载模型（mlx_vlm）…", flush=True)
    GroundingHandler.agent = MaiUiGroundingAgent(cfg)
    GroundingHandler.menu_agent = MaiUiMenuDetectAgent(cfg)
    from mai_ui_agent.mlx_inference import get_model_and_processor, resolve_mlx_model_path

    path = resolve_mlx_model_path(cfg)
    get_model_and_processor(path)
    print(f"[mai_ui] 模型已加载: {path}", flush=True)

    server = HTTPServer((args.host, args.port), GroundingHandler)
    base = f"http://{args.host}:{args.port}"
    print(f"[mai_ui] Grounding: {base}/ground", flush=True)
    print(f"[mai_ui] 一级菜单识别: {base}/detect-menus", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[mai_ui] 已停止", flush=True)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
