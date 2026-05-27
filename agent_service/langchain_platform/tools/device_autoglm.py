"""AutoGLM 设备动作 Tool 封装（供 Skill 注册表扩展）。"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from agent_service.func_agent.backends.autoglm.agent import AgentConfig, PhoneTestAgent
from autoglm_phone_tech.device.device_factory import create_device
from autoglm_phone_tech.device.platform import DevicePlatform
from autoglm_phone_tech.model.client import ModelConfig


def build_phone_test_agent(
    *,
    device_platform: str = "android",
    device_id: str | None = None,
) -> PhoneTestAgent:
    import os

    from agent_service.common.device_resolve import resolve_execution_device_id

    api_key = os.getenv("BIGMODEL_API_KEY") or os.getenv("ZHIPU_API_KEY")
    if not api_key:
        raise RuntimeError("请配置 BIGMODEL_API_KEY 或 ZHIPU_API_KEY")
    plat = DevicePlatform.parse(device_platform)
    resolved = resolve_execution_device_id(run_device_id=device_id, device_platform=plat.value)
    model_config = ModelConfig(
        base_url=os.getenv("OPENAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
        api_key=api_key,
        model_name=os.getenv("PHONE_AGENT_MODEL", "autoglm-phone"),
    )
    agent_config = AgentConfig(
        max_steps=int(os.getenv("PHONE_AGENT_MAX_STEPS", "100")),
        device_id=resolved,
        device_platform=plat.value,
        verbose=False,
    )
    return PhoneTestAgent(model_config=model_config, agent_config=agent_config, print_model_stream=False)


@tool
def list_connected_devices_hint(device_platform: str = "android") -> str:
    """返回设备平台说明（完整列表由 Web devices API 提供）。"""
    plat = DevicePlatform.parse(device_platform)
    return f"当前执行平台：{plat.value}。请通过 Web API GET /api/devices/connected?platform={plat.value} 枚举终端。"


def execute_autoglm_action(agent: PhoneTestAgent, action: dict[str, Any], width: int, height: int) -> Any:
    return agent.action_handler.execute(action, width, height)
