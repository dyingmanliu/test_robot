"""MAI-UI 本地 Grounding Agent（截图 + 自然语言 → UI 元素坐标）。"""

from mai_ui_agent.config import MaiUiConfig, load_config
from mai_ui_agent.grounding import GroundingResult, MaiUiGroundingAgent
from mai_ui_agent.menu_detect import MaiUiMenuDetectAgent, MenuDetectResult, MenuItemResult

__all__ = [
    "MaiUiConfig",
    "load_config",
    "MaiUiGroundingAgent",
    "GroundingResult",
]
