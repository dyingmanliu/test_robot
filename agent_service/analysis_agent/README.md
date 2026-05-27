# analysis_agent

**测试分析机器人** Agent 包：用例生成 + 功能点 / 功能菜单树遍历。

实现已委托 **`agent_service/langchain_platform/`**（LangChain 1.x）；本包保留门面类型与对外类名，便于 Web / OpenAPI 不变。

| 能力 | 门面 | LangChain 实现 | 设备 |
|------|------|----------------|------|
| 用例自动生成 | `agent.py` → `AnalysisAgent` | `CaseGenChain` | 否 |
| 功能点遍历 | `feature_explore/agent.py` → `FeatureExploreAgent` | `ExploreOrchestratorGraph` | 是（Midscene） |

**调用流程（完整时序）**：[`langchain_platform/README.md`](../langchain_platform/README.md)  
**架构总览**：仓库根 [`ARCHITECTURE.md`](../../ARCHITECTURE.md) §1.3、§1.3.1、§4.6

## 目录结构

```
agent_service/analysis_agent/
  agent.py              # AnalysisAgent 门面 → CaseGenChain
  feature_explore/
    agent.py            # FeatureExploreAgent 门面 → explore_run 图
    types.py            # ExploreDispatch / ExploreRunResult
    tree_build.py       # GIIC 树归一化
  types.py              # ProjectContext / CaseDraft / CaseStep
  errors.py
  config/               # CASE_GEN_* 提示词与环境变量
  parser.py             # JSON 解析（CaseGenChain 复用）
  model/client.py       # 遗留 OpenAI SDK 客户端（当前生成路径未使用）
```

## 环境变量

`agent_service/.env`：

| 变量 | 说明 |
|------|------|
| `CASE_GEN_API_KEY` | 优先；缺省回退 `BIGMODEL_API_KEY` |
| `CASE_GEN_BASE_URL` / `CASE_GEN_MODEL` | 用例生成网关与模型 |
| `CASE_GEN_USE_KB` / `CASE_GEN_KB_LIMIT` | KB 开关与条数 |
| `WEB_INTERNAL_API_URL` / `WEB_SERVICE_TOKEN` | agent 侧 Retriever 调 Web internal API |
| `MIDSCENE_*` / `EXPLORE_TRAVERSE_MODE` | 功能点遍历（explore 子进程） |

## Web 侧适配

| 能力 | Web 模块 |
|------|----------|
| 用例生成 | `web/backend/app/services/case_generation.py` |
| 功能点分析 | `web/backend/app/services/feature_analysis_bridge.py` |

HTTP 客户端：`web/backend/app/services/agent_service_client.py`。
