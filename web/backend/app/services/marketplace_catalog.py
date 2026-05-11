"""数字机器人商城：四大品类静态目录（可由配置中心或运营后台替换）。"""

from __future__ import annotations

from typing import Any, Optional

# 计价单位为分（CNY），对接真实计费服务时可改为动态询价

_ROBOTS: list[dict[str, Any]] = [
    {
        "id": "test_analysis",
        "name": "测试分析数字机器人",
        "category": "测试分析",
        "profile": (
            "面向版本迭代与需求变更的智能测试分析助手，聚合用例库、执行历史与缺陷分布，"
            "识别覆盖缺口与高风险模块，输出可执行的测试策略建议。"
        ),
        "capabilities": [
            "需求与用例映射分析，标注未覆盖路径",
            "执行日志与失败模式聚类，定位不稳场景",
            "与项目看板联动，生成简报级测试决策摘要",
        ],
        "billing_modes": {
            "duration": {
                "label": "按时长",
                "unit_label": "每计费小时",
                "price_cents": 2900,
                "description": "按调度与推理占用时长结算，适合深度分析与长会话。",
            },
            "count": {
                "label": "按次数",
                "unit_label": "每次分析任务",
                "price_cents": 900,
                "description": "按单次提交的分析任务计费，适合轻量、碎片化咨询。",
            },
        },
    },
    {
        "id": "functional_execution",
        "name": "功能执行数字机器人",
        "category": "功能执行",
        "profile": (
            "覆盖主流业务路径的端到端功能验证执行体，基于自然语言用例驱动真实设备操作，"
            "适用于回归、冒烟与迭代验收。"
        ),
        "capabilities": [
            "自然语言用例 → UI 自动化执行（ADB / 手机端）",
            "步骤级日志与截图追溯（与测试运行记录打通）",
            "支持项目空间隔离与租户级配额（对接计费模块）",
        ],
        "billing_modes": {
            "duration": {
                "label": "按时长",
                "unit_label": "每计费小时",
                "price_cents": 4500,
                "description": "按机器人在线执行时长计费，适合长链路、多步骤场景。",
            },
            "count": {
                "label": "按次数",
                "unit_label": "每次执行",
                "price_cents": 1200,
                "description": "按单次用例执行计费，适合高频短任务。",
            },
        },
    },
    {
        "id": "specialized_execution",
        "name": "专项执行数字机器人",
        "category": "专项执行",
        "profile": (
            "面向兼容性、弱网、权限与安全专项的定制执行形态，可挂载插件化脚本与设备矩阵，"
            "用于里程碑前冲刺与合规抽检。"
        ),
        "capabilities": [
            "多设备 / 多版本矩阵编排（与设备域对接）",
            "专项场景模板（安装升级、推送、登录态保持等）",
            "报告与缺陷产物回流至项目质量看板",
        ],
        "billing_modes": {
            "duration": {
                "label": "按时长",
                "unit_label": "每计费小时",
                "price_cents": 6200,
                "description": "专项环境占用与编排按小时计费。",
            },
            "count": {
                "label": "按次数",
                "unit_label": "每个专项包",
                "price_cents": 3500,
                "description": "按预置专项包或单次编排计费。",
            },
        },
    },
    {
        "id": "quality_assessment",
        "name": "质量评估数字机器人",
        "category": "质量评估",
        "profile": (
            "从缺陷趋势、执行稳定性与覆盖率维度给出量化质量评分与发布风险提示，"
            "服务于版本门禁与管理层摘要。"
        ),
        "capabilities": [
            "聚合缺陷、执行与报告数据，生成趋势与对比视图",
            "发布就绪度评分与阻塞项列表",
            "输出 Executive Summary，对接邮件 / IM（后续集成）",
        ],
        "billing_modes": {
            "duration": {
                "label": "按时长",
                "unit_label": "每计费小时",
                "price_cents": 3800,
                "description": "交互式评估会话按时长计费。",
            },
            "count": {
                "label": "按次数",
                "unit_label": "每次评估报告",
                "price_cents": 1800,
                "description": "按单次生成的质量评估报告计费。",
            },
        },
    },
]


def list_robots() -> list[dict[str, Any]]:
    return _ROBOTS


def get_robot_by_id(robot_id: str) -> Optional[dict[str, Any]]:
    for r in _ROBOTS:
        if r["id"] == robot_id:
            return r
    return None
