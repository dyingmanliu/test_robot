"""Midscene YAML 用例校验与默认模板。"""

from __future__ import annotations

DEFAULT_MIDSCENE_YAML_TEMPLATE = """# Midscene HarmonyOS 用例（runYaml 仅执行 tasks 段；设备由服务端 HDC 环境连接）
tasks:
  - name: 示例任务
    flow:
      - ai: 打开设置应用
      - sleep: 1000
      - aiAssert: 页面显示设置项列表
"""


def validate_case_yaml(raw: str) -> str:
    """校验并返回规范化后的 YAML 文本。"""
    text = (raw or "").strip()
    if not text:
        raise ValueError("YAML 用例内容不能为空")
    if "tasks:" not in text:
        raise ValueError("YAML 须包含 tasks: 段（Midscene 脚本格式）")
    try:
        import yaml as pyyaml
    except ImportError as e:
        raise RuntimeError("请安装 PyYAML：pip install pyyaml") from e
    try:
        doc = pyyaml.safe_load(text)
    except pyyaml.YAMLError as e:
        raise ValueError(f"YAML 语法错误: {e}") from e
    if not isinstance(doc, dict):
        raise ValueError("YAML 根节点须为对象")
    tasks = doc.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("tasks 须为非空列表")
    return text
