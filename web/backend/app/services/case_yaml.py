"""Midscene YAML 用例校验与默认模板。"""

from __future__ import annotations

DEFAULT_MIDSCENE_YAML_TEMPLATE = """# Midscene YAML 用例（仅 tasks 段由 runYaml 执行）
# - 设备：由用例页所选「平台 + 目标终端」连接（Android ADB / 鸿蒙 HDC）
# - 须使用 test_agent_backend=midscene 的机器人实例执行
# - flow 常用指令：ai（自然语言操作）、aiAssert（断言）、sleep（毫秒）
# 文档：https://midscenejs.com/automate-with-scripts-in-yaml

tasks:
  - name: 美团搜索火锅并进入商户详情
    flow:
      - ai: 确保满足前置条件：已登录美团 App，网络正常
      - ai: 打开美团 App；若不在首页则返回首页
      - sleep: 2000
      - aiAssert: 当前为美团首页，能看到顶部搜索框或「搜索」入口
      - ai: 点击首页搜索框
      - sleep: 1000
      - aiAssert: 已进入搜索页，能看到搜索输入框
      - ai: 在搜索框输入「火锅」并点击搜索或键盘确认
      - sleep: 2000
      - aiAssert: 已进入搜索结果页，列表中有火锅相关商户
      - ai: 点击列表中第一家火锅店，进入商户详情
      - sleep: 1500
      - aiAssert: 已进入商户详情页，能看到店名、评分或「加入购物车」等入口
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
