#!/usr/bin/env python3
"""Unified CLI entrypoint for functional test agent."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

from agent_service.func_agent.backends.autoglm.agent import AgentConfig, PhoneTestAgent
from autoglm_phone_tech.device.adb_resolve import resolve_adb_executable
from autoglm_phone_tech.device.hdc_resolve import resolve_hdc_executable
from autoglm_phone_tech.device.platform import DevicePlatform
from autoglm_phone_tech.model.client import ModelConfig


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


def _check_hdc() -> None:
    hdc = resolve_hdc_executable(os.getenv("HDC_HOME"))
    try:
        r = subprocess.run([hdc, "list", "targets"], capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            print("警告: hdc list targets 执行异常", file=sys.stderr)
            return
        lines = [ln.strip() for ln in (r.stdout or "").splitlines() if ln.strip()]
        if not lines:
            print("警告: 未检测到鸿蒙设备，请连接设备并开启 USB 调试。", file=sys.stderr)
    except FileNotFoundError:
        print("错误: 未找到 hdc，请安装 DevEco Studio 并配置 HDC_HOME 或 PATH。", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("警告: hdc list targets 超时", file=sys.stderr)


def main() -> None:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    parser = argparse.ArgumentParser(description="功能测试机器人（func_agent）CLI")
    parser.add_argument("task", nargs="?", default="", help="自然语言测试任务 / 用户指令")
    parser.add_argument("--max-steps", type=int, default=100)
    parser.add_argument(
        "--device-type",
        choices=["adb", "hdc", "android", "harmonyos"],
        default=os.getenv("PHONE_AGENT_DEVICE_TYPE", "adb"),
        help="设备类型：adb/android=Android，hdc/harmonyos=鸿蒙",
    )
    parser.add_argument("--device-id", default=None, help="设备 ID（adb serial 或 hdc target）")
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

    platform = DevicePlatform.parse(args.device_type)
    if platform == DevicePlatform.HARMONYOS:
        _check_hdc()
        default_device_id = os.getenv("HDC_DEVICE_ID")
    else:
        _check_adb()
        default_device_id = os.getenv("ADB_DEVICE_ID")

    model_config = ModelConfig(
        base_url=args.base_url,
        api_key=api_key,
        model_name=args.model,
    )
    agent_config = AgentConfig(
        max_steps=args.max_steps,
        device_id=args.device_id or default_device_id or None,
        device_platform=platform.value,
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
