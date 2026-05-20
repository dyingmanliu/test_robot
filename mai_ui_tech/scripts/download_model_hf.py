#!/usr/bin/env python3
"""从 Hugging Face（或 HF 镜像）下载 MAI-UI-2B MLX 权重到本地目录。"""

from __future__ import annotations

import argparse
import os
import sys

# 候选仓库（按优先级）
DEFAULT_REPOS = (
    "mlx-community/MAI-UI-2B-bf16-v2",
    "mlx-community/MAI-UI-2B-bf16",
)


def _hub_endpoint() -> str | None:
    for key in ("HF_ENDPOINT", "HUGGINGFACE_HUB_ENDPOINT", "HUGGINGFACE_HUB_BASE_URL"):
        val = (os.getenv(key) or "").strip().rstrip("/")
        if val:
            return val
    return None


def _download_one(repo_id: str, local_dir: str, endpoint: str | None) -> str:
    from huggingface_hub import snapshot_download

    kwargs: dict = {
        "repo_id": repo_id,
        "local_dir": local_dir,
    }
    if endpoint:
        kwargs["endpoint"] = endpoint
        # 部分版本仍读环境变量，双保险
        os.environ["HF_ENDPOINT"] = endpoint
        os.environ["HUGGINGFACE_HUB_ENDPOINT"] = endpoint

    print(f"  endpoint={endpoint or 'https://huggingface.co (官方)'}")
    return snapshot_download(**kwargs)


def main() -> int:
    parser = argparse.ArgumentParser(description="Download MAI-UI-2B MLX weights")
    parser.add_argument(
        "--repo",
        default=os.getenv("MAI_UI_MLX_MODEL", ""),
        help="Hugging Face repo id（默认依次尝试 v2 / bf16）",
    )
    parser.add_argument(
        "--local-dir",
        default=os.getenv(
            "MAI_UI_MODEL_DIR",
            os.path.join(os.path.dirname(__file__), "..", "models", "MAI-UI-2B-bf16-v2"),
        ),
        help="Local directory to save weights",
    )
    parser.add_argument(
        "--endpoint",
        default=_hub_endpoint() or "https://hf-mirror.com",
        help="Hub 地址；国内默认 hf-mirror.com，海外可传 --endpoint https://huggingface.co",
    )
    args = parser.parse_args()
    local_dir = os.path.abspath(args.local_dir)
    endpoint = (args.endpoint or "").strip().rstrip("/") or None

    try:
        from huggingface_hub import snapshot_download  # noqa: F401
    except ImportError:
        print("请先安装: pip install huggingface_hub", file=sys.stderr)
        return 1

    repos = [args.repo] if args.repo else list(DEFAULT_REPOS)
    os.makedirs(local_dir, exist_ok=True)

    print(f"目标目录: {local_dir}")
    if endpoint:
        print(f"HF 镜像/端点: {endpoint}")

    last_err: Exception | None = None
    for repo_id in repos:
        print(f"\n尝试下载: {repo_id}")
        try:
            path = _download_one(repo_id, local_dir, endpoint)
            print(f"\n完成: {path}")
            print("\n在 .env 中设置:")
            print(f"  MAI_UI_MODEL={local_dir}")
            return 0
        except Exception as e:
            last_err = e
            print(f"  失败: {e}", file=sys.stderr)

    print("\n全部仓库下载失败。可尝试:", file=sys.stderr)
    print("  1) 开 VPN 后: export HF_ENDPOINT= && python scripts/download_model_hf.py --endpoint https://huggingface.co", file=sys.stderr)
    print("  2) 浏览器打开 https://hf-mirror.com/mlx-community/MAI-UI-2B-bf16-v2 手动下载到 models/MAI-UI-2B-bf16-v2/", file=sys.stderr)
    print("  3) 终端代理: export HTTPS_PROXY=http://127.0.0.1:7890", file=sys.stderr)
    if last_err:
        print(f"\n最后错误: {last_err}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
