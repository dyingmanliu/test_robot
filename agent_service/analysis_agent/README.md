# analysis_agent

**测试分析机器人** Agent 包，包含两类能力：

| 能力 | 模块 | 设备 | 环境变量 |
|------|------|------|----------|
| 用例自动生成 | `agent.py` → `AnalysisAgent` | 否 | `CASE_GEN_*` |
| 功能点 / 功能菜单树遍历 | `feature_explore/` → `FeatureExploreAgent` | 是（Midscene） | `MIDSCENE_*` |

用例生成与 `autoglm_phone_tech`（测试执行）分离；功能点遍历通过 **Midscene explore 子进程**（`midscene_tech/src/explore.ts`）操作真机，由 Web 适配层 `feature_analysis_bridge.py` 持久化任务与日志。

**说明**：本包不生成 Midscene YAML。若 Web 端请求 `case_format=yaml` 或用户在编辑弹窗切换为 YAML，由 `web/backend/app/services/case_format_convert.py` 在 structured 字段与 `tasks:` 脚本之间做规则转换（见根目录 `ARCHITECTURE.md` §1.3）。

## 目录结构

```
agent_service/analysis_agent/
  agent.py              # AnalysisAgent — 用例生成
  feature_explore/      # FeatureExploreAgent — 功能树 DFS 编排
    agent.py
    types.py
  types.py              # ProjectContext / CaseDraft / CaseStep
  errors.py
  config/               # CASE_GEN_* 环境变量、系统提示
  model/client.py       # OpenAI 兼容 chat.completions
  parser.py             # JSON 解析与校验
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
from agent_service.analysis_agent import AnalysisAgent, ProjectContext

agent = AnalysisAgent()
draft = agent.generate_case_draft(
    project=ProjectContext(name="...", tested_app_name="美团", test_objective="..."),
    prompt="在美团点一杯奶茶",
    kb_snippets=["【参考用例 ...】\n..."],
)
```

- 用例生成适配层：`web/backend/app/services/case_generation.py`；格式互见 `case_format_convert.py` 与 `POST /api/test-cases/convert-format`。
- 功能点分析适配层：`web/backend/app/services/feature_analysis_bridge.py`；API 前缀 `/api/projects/{id}/feature-analysis`。
