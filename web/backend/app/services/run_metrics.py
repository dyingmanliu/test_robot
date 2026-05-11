"""执行记录度量：从 step_log（JSON Lines）统计模型推理/识别步数。"""

from __future__ import annotations


def count_recognition_steps(step_log: str | None) -> int:
    """每条非空行对应 Agent 一步推理（含屏幕理解与动作决策），作为「识别次数」口径。"""
    if not step_log or not str(step_log).strip():
        return 0
    return sum(1 for line in str(step_log).strip().split("\n") if line.strip())
