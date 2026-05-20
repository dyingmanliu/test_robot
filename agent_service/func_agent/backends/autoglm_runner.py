from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv


def _resolve_repo_root() -> Path:
    cur = Path(__file__).resolve()
    for parent in cur.parents:
        if (parent / "web" / "backend").is_dir() and (parent / "autoglm_phone_tech").is_dir():
            return parent
    return cur.parents[3]


_REPO_ROOT = _resolve_repo_root()


def run_autoglm_task(
    task: str,
    *,
    device_platform: str = "android",
    device_id: str | None = None,
    on_step: Callable[[int, Any], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
):
    """Runs AutoGLM functional agent in-process (blocking)."""
    load_dotenv(_REPO_ROOT / ".env")
    os.chdir(_REPO_ROOT)

    from agent_service.func_agent.backends.autoglm.agent import AgentConfig, PhoneTestAgent
    from autoglm_phone_tech.device.platform import DevicePlatform
    from autoglm_phone_tech.model.client import ModelConfig
    from app.services.device_platform import resolve_execution_device_id

    api_key = os.getenv("BIGMODEL_API_KEY") or os.getenv("ZHIPU_API_KEY")
    if not api_key:
        raise RuntimeError("请配置 BIGMODEL_API_KEY 或 ZHIPU_API_KEY（环境变量或项目根目录 .env）")

    plat = DevicePlatform.parse(device_platform)
    resolved_device_id = resolve_execution_device_id(
        run_device_id=device_id,
        device_platform=plat.value,
    )

    model_config = ModelConfig(
        base_url=os.getenv("OPENAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
        api_key=api_key,
        model_name=os.getenv("PHONE_AGENT_MODEL", "autoglm-phone"),
    )
    agent_config = AgentConfig(
        max_steps=int(os.getenv("PHONE_AGENT_MAX_STEPS", "100")),
        device_id=resolved_device_id,
        device_platform=plat.value,
        verbose=False,
    )
    agent = PhoneTestAgent(
        model_config=model_config,
        agent_config=agent_config,
        print_model_stream=False,
    )
    return agent.run(task.strip(), on_step=on_step, should_cancel=should_cancel)
