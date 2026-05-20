"""AutoGLM backend resources (device/model/config helpers).

Execution entrypoints are unified under ``agent_service/func_agent``.
"""

from autoglm_phone_tech.model.client import ModelClient, ModelConfig, ModelResponse

__all__ = ["ModelClient", "ModelConfig", "ModelResponse"]
