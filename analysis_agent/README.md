# analysis_agent

测试用例**分析 / 编写** Agent：将用户一句话转为 **structured** 用例草稿（标题、前置条件、步骤、执行说明）。

与 `autoglm_phone_tech`（设备执行）并列，由 Web 后端**同进程**导入调用，不操作手机。

**说明**：本包不生成 Midscene YAML。若 Web 端请求 `case_format=yaml` 或用户在编辑弹窗切换为 YAML，由 `web/backend/app/services/case_format_convert.py` 在 structured 字段与 `tasks:` 脚本之间做规则转换（见根目录 `ARCHITECTURE.md` §1.3）。

## 目录结构

```
analysis_agent/
  agent.py           # AnalysisAgent 入口
  types.py           # ProjectContext / CaseDraft / CaseStep
  errors.py
  config/            # CASE_GEN_* 环境变量、系统提示
  model/client.py    # OpenAI 兼容 chat.completions
  parser.py          # JSON 解析与校验
```

## 环境变量

仓库根 `.env`（与 Web / AutoGLM 共用）：

| 变量 | 说明 |
|------|------|
| `CASE_GEN_API_KEY` | 优先；缺省回退 `BIGMODEL_API_KEY` |
| `CASE_GEN_BASE_URL` | OpenAI 兼容网关 |
| `CASE_GEN_MODEL` | 模型名，默认 `glm-4-flash` |
| `CASE_GEN_TIMEOUT_SEC` | 超时（秒） |

RAG 检索由 Web 层 `case_kb` 完成，结果以 `kb_snippets` 传入 Agent。

## Web 调用示例

```python
from analysis_agent import AnalysisAgent, ProjectContext

agent = AnalysisAgent()
draft = agent.generate_case_draft(
    project=ProjectContext(name="...", tested_app_name="美团", test_objective="..."),
    prompt="在美团点一杯奶茶",
    kb_snippets=["【参考用例 ...】\n..."],
)
```

适配层见 `web/backend/app/services/case_generation.py`；格式互见 `case_format_convert.py` 与 `POST /api/test-cases/convert-format`。
