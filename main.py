#!/usr/bin/env python3
"""
CLI entrypoint — natural-language Android APP automation via AutoGLM-Phone (智谱).

Usage:
  export BIGMODEL_API_KEY=...
  python main.py "打开美团搜索附近的火锅店"

环境: Python 3.10+, ADB, Android 设备已连接（adb devices）。
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

from autoglm_phone_agent.agent import AgentConfig, PhoneTestAgent
from autoglm_phone_agent.device.adb_resolve import resolve_adb_executable
from autoglm_phone_agent.model.client import ModelConfig


def _check_adb() -> None:
    try:
        adb = resolve_adb_executable()
    except FileNotFoundError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    try:
        r = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            print("警告: adb devices 执行异常", file=sys.stderr)
            return
        lines = [ln for ln in r.stdout.strip().splitlines() if ln.strip() and not ln.startswith("List")]
        devices = [ln for ln in lines if "\tdevice" in ln]
        if not devices:
            print("警告: 未检测到已连接的设备，请先连接手机并开启 USB 调试。", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print("警告: adb devices 超时", file=sys.stderr)


def main() -> None:
    # 从项目根目录加载 .env（与当前工作目录无关）
    load_dotenv(Path(__file__).resolve().parent / ".env")
    parser = argparse.ArgumentParser(description="AutoGLM-Phone APP 自动化测试智能体")
    parser.add_argument("task", nargs="?", default="", help="自然语言测试任务 / 用户指令")
    parser.add_argument("--max-steps", type=int, default=100)
    parser.add_argument("--device-id", default=os.getenv("ADB_DEVICE_ID") or None)
    parser.add_argument("--base-url", default=os.getenv("OPENAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"))
    parser.add_argument("--model", default=os.getenv("PHONE_AGENT_MODEL", "autoglm-phone"))
    parser.add_argument("--quiet-model-stream", action="store_true", help="不向终端打印模型流式输出")
    args = parser.parse_args()

    api_key = os.getenv("BIGMODEL_API_KEY") or os.getenv("ZHIPU_API_KEY")
    if not api_key:
        print("请设置环境变量 BIGMODEL_API_KEY（智谱开放平台 API Key）", file=sys.stderr)
        sys.exit(1)

    task = args.task.strip()
    if not task:
        task = input("请输入自然语言任务: ").strip()
    if not task:
        print("未提供任务描述", file=sys.stderr)
        sys.exit(1)

    _check_adb()

    model_config = ModelConfig(
        base_url=args.base_url,
        api_key=api_key,
        model_name=args.model,
    )
    agent_config = AgentConfig(
        max_steps=args.max_steps,
        device_id=args.device_id,
        verbose=True,
    )
    agent = PhoneTestAgent(
        model_config=model_config,
        agent_config=agent_config,
        print_model_stream=not args.quiet_model_stream,
    )
    final = agent.run(task)
    print("\n--- 最终结果 ---\n", final.message)
    sys.exit(0 if final.ok else 1)


if __name__ == "__main__":
    main()
