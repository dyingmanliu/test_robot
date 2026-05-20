#!/usr/bin/env python3
"""CLI：对单张截图做 MAI-UI Grounding。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mai_ui_tech.grounding import MaiUiGroundingAgent
from mai_ui_tech.health import check_server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="MAI-UI-2B 本地 Grounding：根据截图与文字描述定位 UI 元素",
    )
    parser.add_argument("--image", "-i", help="截图路径（PNG/JPEG）")
    parser.add_argument("--query", "-q", help="要定位的控件描述，如「登录按钮」")
    parser.add_argument(
        "--queries",
        nargs="+",
        help="批量 query（与 --query 二选一）",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="仅检查 MAI_UI_BASE_URL 是否可达后退出",
    )
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    args = parser.parse_args(argv)

    if args.check:
        ok, msg = check_server()
        print(msg)
        return 0 if ok else 1

    if not args.image:
        print("请提供 --image（或使用 --check）", file=sys.stderr)
        return 1

    image_path = Path(args.image)
    if not image_path.is_file():
        print(f"图片不存在: {image_path}", file=sys.stderr)
        return 1

    queries = args.queries or ([args.query] if args.query else [])
    if not queries:
        print("请提供 --query 或 --queries", file=sys.stderr)
        return 1

    agent = MaiUiGroundingAgent()
    results = [agent.ground(q, image_path).to_dict() for q in queries]

    if args.json:
        print(json.dumps(results if len(results) > 1 else results[0], ensure_ascii=False, indent=2))
    else:
        for r in results:
            print(f"\n=== {r['instruction']} ===")
            if not r["ok"]:
                print(f"失败: {r['error']}")
                continue
            print(f"归一化: {r['coordinate_norm']}")
            print(f"0-999:  {r['coordinate_999']}")
            print(f"0-1000: {r['coordinate_1000']}")
            print(f"像素:   {r['coordinate_px']}  (图 {r['image_width']}x{r['image_height']})")
            if r.get("thinking"):
                print(f"思考: {r['thinking'][:200]}...")

    return 0 if all(r["ok"] for r in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
