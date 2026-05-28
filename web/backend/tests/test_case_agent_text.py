"""case_agent_text：Midscene 拆步与 agent_task 拼接。"""

from app.services.case_agent_text import build_agent_task_text, build_midscene_tech_steps

_CASE16_STEPS = """[
  {"order": 1, "description": "在联系人App首页点击添加按钮。", "expected": "进入新建页。"},
  {"order": 2, "description": "在姓名字段中输入「试测」。", "expected": "显示试测。"},
  {"order": 3, "description": "在手机号字段中输入「13600000000」。", "expected": "显示号码。"},
  {"order": 4, "description": "点击保存。", "expected": "保存成功。"},
  {"order": 5, "description": "在列表中查找该记录。", "expected": "列表中有试测。"}
]"""

_TASK_TEXT = (
    "核心断言需校验保存后列表数据与输入值完全一致；"
    "注意处理通讯录权限弹窗。"
)


def test_midscene_steps_omit_task_text_when_structured_steps_exist():
    steps = build_midscene_tech_steps(
        task_text=_TASK_TEXT,
        preconditions="已打开联系人 App。",
        steps_json=_CASE16_STEPS,
    )
    assert steps is not None
    assert len(steps) == 5
    assert not any("【执行说明】" in s for s in steps)
    assert not any("核心断言" in s for s in steps)


def test_midscene_steps_use_task_text_when_no_structured_steps():
    steps = build_midscene_tech_steps(
        task_text="打开设置并检查版本号。",
        preconditions="",
        steps_json="[]",
    )
    assert steps is None

    steps_one = build_midscene_tech_steps(
        task_text="仅执行说明中的任务。",
        preconditions="",
        steps_json="[]",
        min_steps=1,
    )
    assert steps_one == ["仅执行说明中的任务。"]


def test_agent_task_still_includes_task_text():
    full = build_agent_task_text(
        task_text=_TASK_TEXT,
        preconditions="已打开 App。",
        steps_json=_CASE16_STEPS,
    )
    assert "【执行说明】" in full
    assert "核心断言" in full


if __name__ == "__main__":
    test_midscene_steps_omit_task_text_when_structured_steps_exist()
    test_midscene_steps_use_task_text_when_no_structured_steps()
    test_agent_task_still_includes_task_text()
    print("ok")
