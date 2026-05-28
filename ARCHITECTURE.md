# 测试用例管理平台 — 架构说明（维护向）

本文档描述本仓库的技术架构与目录约定，供初级工程师维护代码时查阅。

**近期架构要点（2025–2026）**

- **三进程 + 向量库**：Vue (:5173) → Web 后端 (:8000) → **agent_service** (:8100)；**MySQL 8** + **Qdrant**（:6333）双存储；长任务经 **HTTP POST + SSE**，取消经 **DELETE**。
- **LangChain 1.x**：测试分析编排与用例生成、功能测试执行调度均在 `agent_service/langchain_platform/`（`langchain-core` 1.4.x、`langgraph` 1.2.x）；`analysis_agent` / `func_agent` 为薄门面。
- **用例格式**：仅 **structured**（`steps_json` + `task_text`）；Midscene 执行走 **natural** 模式，Web 层不再使用 YAML。
- **Agentic RAG 知识库**：MySQL 元数据 + **Qdrant** 向量 + ingest/query（`web/backend/app/knowledge/`）+ LangGraph **Tool**；规范类文档须平台管理员审核后入向量库。详见 **§4.8**。
- **KB（兼容）**：Web `case_kb` 预检索 + `GET /api/internal/knowledge/cases/search`（语义检索优先，LIKE 降级）。
- **日志**：Web 与 agent_service 共用 `LOG_LEVEL` / `LOG_FORMAT` 风格（毫秒时间戳 + 模块 + 文件行号）；agent 见 `agent_service/service/logging_config.py`。
- **用例生成（异步）**：Web `POST /api/test-cases/generate` 返回 **202 + `job_id`**，内存 Job（`case_generation_jobs`）消费 agent **202 + SSE**；前端轮询 `GET …/generate/{job_id}` 展示 `step_log`（含 KB/LLM 明细）。避免长耗时同步 HTTP 超时。
- **功能树版本命名**：确认保存时 `version_label` 默认 **`{应用名}-vN`**（同应用下兼容旧版纯 `vN` 序号）；同步知识库时旧版纯 `vN` 标题会补应用名便于检索。

## 1. 系统定位

### 1.0 数字机器人 × Agent 边界（概念与扩展）

Web 将租用的**数字机器人实例**按商城 **功能定位（`catalog_robot_id` 等）** 区分能力；**FastAPI 按实例类型把请求路由到不同的 Agent 实现**。与本仓库源码直接对应的归类如下：

| 业务定位（示例） | 代码侧 Agent | 说明 |
|------------------|--------------|------|
| **测试分析机器人** | `agent_service/analysis_agent/` + `langchain_platform/` | **用例生成**：LangChain `CaseGenChain` → structured（`CASE_GEN_*`，**不连真机**）。**功能点分析**：`ExploreOrchestratorGraph` → Midscene `explore`（`MIDSCENE_*`） |
| **测试执行机器人（func_agent）** | `agent_service/func_agent/`（内含 `autoglm_phone_tech/` 与 `midscene_tech/` 技术后端） | **同一业务定位下的两条技术路线**：LLM 驱动 UI（智谱 AutoGLM-Phone）与视觉驱动 UI（Midscene.js）。由实例字段 **`test_agent_backend`**（`autoglm` \| `midscene`）与 **`device_platform`** 在 `executor.py` 中择路；均经 ADB/HDC 操作真机 |
| **其他功能定位**（专项执行、质量评估等） | 未来各自 **独立 Agent 包 + 路由/服务** | 与 `case_generation`、`executor` 平行扩展；本架构图以虚线占位，不展开具体实现 |

**要点**：`autoglm_phone_tech` 与 `midscene_tech` 在业务上统一归属 **`agent_service/func_agent`（功能测试机器人）**，不是与「测试分析」并列的第三、第四种「机器人类型」；后续若增加新的测试执行技术路线，仍在 `agent_service/func_agent` 域内扩展并由 `executor` 分支选择。

本仓库还包含：

1. **`agent_service/analysis_agent/`（Python）** — **测试分析机器人 Agent**：**用例生成**（`AnalysisAgent`，无真机，Web 适配 `case_generation.py`）；**功能点分析**（`FeatureExploreAgent`，Midscene explore 子进程，Web 适配 `feature_analysis_bridge.py`）。详见 [`agent_service/analysis_agent/README.md`](./agent_service/analysis_agent/README.md)。

2. **`agent_service/func_agent/`（Python）** — **功能测试机器人门面**：`orchestrator` → `FuncDispatchGraph`；内部两条后端（AutoGLM / Midscene）。

3. **`autoglm_phone_tech/`（Python）** 与 **`midscene_tech/`（Node）** — **func_agent 技术后端实现**：前者为观察→推理→执行（ADB/HDC），后者为视觉自动化（`@midscene/android` / `@midscene/harmony`，Web 子进程 `--web-dispatch`）。

4. **`web/`（Web 应用）**  
   **前端**：项目与用例 CRUD、自动生成草稿、触发执行、轮询步骤日志与结果。  
   **后端**：认证与持久化；经 **`agent_service_client.py`** HTTP 调用 agent_service；**用例生成** → `CaseGenChain`；**功能点分析** → `ExploreOrchestratorGraph` + Midscene explore；**测试执行** → `FuncDispatchGraph` → AutoGLM 同进程或 Midscene 子进程。

5. **`agent_service/langchain_platform/`（Python）** — **LangChain 1.x 统一实现层**：LCEL 链、LangGraph 编排、Retriever、Tool；对外 HTTP/SSE **契约不变**。详见 §1.3.1、[`langchain_platform/README.md`](./agent_service/langchain_platform/README.md)。

6. **`mai_ui_tech/`（Python）** — **GUI Grounding 技术路线**：本地 MAI-UI 推理与坐标解析；由 Web 服务 `mai_ui_service.py` 对接 `/api/mai-ui/*` 能力。

### 1.1 测试执行：技术路线 × 设备平台（`test_agent_backend` × `device_platform`）

下列矩阵描述 **测试执行机器人** 在选定实例后，如何落到底层包与设备（**不是**测试分析机器人的行为）：

| 技术路线 `test_agent_backend` | `device_platform` | 实际执行链路 |
|----------------------|-------------------|--------------|
| `autoglm` | `android` | `autoglm_phone_tech` + ADB（智谱，参考 [Open-AutoGLM](https://github.com/zai-org/Open-AutoGLM)） |
| `autoglm` | `harmonyos` | `autoglm_phone_tech` + HDC / uitest（同 Open-AutoGLM `--device-type hdc`） |
| `midscene` | `android` | `midscene_tech` + `@midscene/android` |
| `midscene` | `harmonyos` | `midscene_tech` + `@midscene/harmony`（千问/GLM 等） |

- 字段定义：`robot_instances.test_agent_backend`、`robot_instances.device_platform`（**默认**执行平台，可在用例页被覆盖）
- 解析与路由：`web/backend/app/services/device_platform.py`、`web/backend/app/executor.py`

### 1.2 测试执行时的设备选择（平台 + 终端）

同一机器人实例**不必**为 Android / 鸿蒙各租一台；执行前在「测试用例」页动态指定：

| 层级 | 字段 / UI | 说明 |
|------|-----------|------|
| 实例默认 | `robot_instances.device_platform` | 「我的机器人」中配置的默认平台（Android / 鸿蒙） |
| 本次平台 | 请求体 `device_platform` → `test_runs.device_platform` | 用例页「本次执行设备」；未传则用实例默认 |
| 本次终端 | 请求体 `device_id` → `test_runs.device_id` | 用例页「目标终端」；ADB serial 或 HDC target ID |
| 环境兜底 | `ADB_DEVICE_ID` / `HDC_DEVICE_ID` | 未在界面选择终端时使用 |

- **枚举在线设备**：`GET /api/devices/connected?platform=android|harmonyos`（`adb devices -l` / `hdc list targets`），实现见 `app/services/device_discovery.py`。
- **投屏**：`GET /api/robot-instances/{id}/device-screen?device_platform=&device_id=`，与本次执行选择一致。
- **解析**：`resolve_execution_platform()`、`resolve_execution_device_id()`（`device_platform.py`）。
- 前端在 `CasesView.vue` 选择机器人 / 平台 / 终端；浏览器 `sessionStorage` 按实例记住上次平台与终端。
- **跨页实时执行**：Pinia `activeTestRun` 轮询 `GET /api/test-cases/runs/{id}`；离开用例页后顶栏可跳转 `/runs/:runId/live`（`RunExecutionLiveView.vue` + `RunLivePanel.vue`）。`RobotInstanceOut.active_run_id` 与 `runtime_status=executing` 供「我的机器人」列表展示 **执行详情** 入口。
- **跨页功能点分析**：`RobotInstanceOut.active_feature_analysis_run_id` / `active_feature_analysis_project_id` 与 `runtime_status=executing` 供「我的机器人」展示 **分析详情**，跳转 `/projects/:projectId/feature-analysis?runId=`；`ProjectFeatureAnalysisView` 按 `runId` 恢复轮询 `step_log` 与投屏。

### 1.3 测试分析机器人 Agent：用例生成（结构化）与功能点分析（explore）

**用例生成**流程见下图；**功能点分析**时序见 §4.6。

**用例生成**与 §1.1 **测试执行** 分离：生成路径不调用 `PhoneTestAgent`；LLM 在 **agent_service** 内经 **LangChain `CaseGenChain`**（`langchain-openai`）产出 **structured** 字段。

**功能点遍历**经 **`ExploreOrchestratorGraph`** 编排后调用 Midscene `explore` 子进程；与用例生成、同实例其它占用互斥。详见 §1.3.1、§4.6。

| 项 | 说明 |
|----|------|
| 包 | `agent_service/analysis_agent/`（门面）+ `langchain_platform/`（实现） |
| Web 适配 | `case_generation.py`（预检 + KB）+ `case_generation_jobs.py`（Job + SSE 消费） |
| 生成路由 | `POST /api/test-cases/generate`（**202** `job_id`）；`GET …/generate/{job_id}` 轮询；成功体 `TestCaseGenerateOut` |
| 持久化 | 上述接口**不写库**；用户在前端编辑后 `POST /api/test-cases` 保存 |
| LLM 输出 | 始终结构化（标题、前置条件、步骤 JSON、执行说明、优先级） |
| 上下文 | `Project.name`、`tested_app_name`、`test_objective` + 用户 `prompt` |
| RAG | Web 侧 `case_kb.search_cases_kb` → `kb_snippets`；agent 侧可选 `WebCaseKbRetriever`（§1.3.1） |
| 执行衔接 | structured → `build_agent_task_text()`；Midscene 拆步 → `build_midscene_tech_steps()` → `agent_steps` |

**注意**：用例已统一为结构化格式（不再支持 YAML）。所有用例通过 `steps_json` + `task_text` 描述步骤，Midscene 执行使用 natural 模式自动转换。存在结构化步骤时，**`task_text`（执行说明）仅并入 `agent_task` 上下文，不单独作为 `agent_steps` 一步**，避免 Midscene 将说明性文字再执行一遍（如重复新建联系人）。

**配置**：`agent_service/.env` 的 `CASE_GEN_*`；KB Retriever 另需 `WEB_SERVICE_TOKEN`（与 `web/backend/.env` 一致）。详见 §6。

### 1.3.1 LangChain 1.x 统一层（`agent_service/langchain_platform/`）

测试分析（用例生成、功能点分析编排）与功能测试执行（AutoGLM / Midscene）**默认**经 **LangChain 1.x + LangGraph** 实现；对外 HTTP/SSE 路径与 payload **不变**（Web 仍通过 `agent_service_client.py` 调用）。

| 能力 | 入口（门面） | LangChain 实现 |
|------|--------------|----------------|
| 用例生成 | `AnalysisAgent.generate_case_draft` | `CaseGenChain`（LCEL + `ChatOpenAI`） |
| 功能点分析 | `FeatureExploreAgent.run` | `ExploreOrchestratorGraph` → `explore_core` → Midscene |
| 测试执行 | `run_func_agent_dispatch` | `FuncDispatchGraph` → `AutoglmExecGraph` \| `MidsceneExecGraph` |

| 模块 | 路径 |
|------|------|
| 配置 / 模型工厂 | `langchain_platform/config.py`、`models.py` |
| 用例生成 | `langchain_platform/chains/case_generation.py` |
| KB Retriever | `langchain_platform/retrievers/web_case_kb.py` |
| 功能点分析 | `graphs/explore_run.py`、`explore_core.py` |
| 执行调度 | `graphs/func_dispatch.py`、`autoglm_exec.py`、`midscene_exec.py` |
| 设备 / 子进程 Tool | `tools/device_autoglm.py`、`tools/midscene_dispatch.py` |
| Skill 注册 | `tools/registry.py` |
| SSE 回调 | `callbacks/sse.py` |

依赖（仅 `agent_service`）：`langchain-core` 1.4.x、`langchain-openai` 1.2.x、`langgraph` 1.2.x、`openai` 2.x。调用流程详见 [`langchain_platform/README.md`](./agent_service/langchain_platform/README.md)。

#### 用例生成调用链

```mermaid
sequenceDiagram
  participant UI as CasesView
  participant API as test_cases_router
  participant Jobs as case_generation_jobs
  participant Gen as case_generation
  participant KB as case_kb
  participant Client as agent_service_client
  participant Router as analysis_router
  participant AA as AnalysisAgent
  participant Graph as CaseGenAgenticGraph
  participant LLM as ChatOpenAI_CASE_GEN

  UI->>API: POST /api/test-cases/generate
  API->>Jobs: start_case_generation_job（后台线程）
  API-->>UI: 202 job_id
  Jobs->>Gen: 预检实例 / 项目权限
  Jobs->>KB: search_cases_kb（可选）
  Jobs->>Client: POST …/generate-case-draft
  Client->>Router: 202 task_id
  Jobs->>Client: GET …/generate-case-draft/{id}/stream（SSE）
  Router->>AA: generate_case_draft（on_progress）
  AA->>Graph: invoke（Agentic RAG / passive 链）
  Graph->>LLM: chat
  LLM-->>Graph: JSON
  Router-->>Client: SSE progress / done
  Client-->>Jobs: 追加 step_log
  loop 轮询约 1.5–2s
    UI->>API: GET /api/test-cases/generate/{job_id}
    API-->>UI: status, progress_message, step_log
  end
  Jobs-->>API: draft（success）
  API-->>UI: TestCaseGenerateOut → 预填编辑弹窗
  UI->>API: POST /api/test-cases（用户确认后写库）
```

#### 功能点分析调用链

```mermaid
sequenceDiagram
  participant UI as FeatureAnalysisView
  participant Bridge as feature_analysis_bridge
  participant Client as agent_service_client
  participant Explore as explore_router
  participant FE as FeatureExploreAgent
  participant Graph as ExploreOrchestratorGraph
  participant Core as explore_core
  participant MS as midscene_explore_subprocess

  UI->>Bridge: POST /feature-analysis/runs（异步）
  Bridge->>Client: submit_explore_run
  Client->>Explore: POST /api/agent/explore/run
  Explore->>FE: run(dispatch)
  FE->>Graph: run_explore_graph
  Graph->>Graph: validate → run_explore → sync_tree
  Graph->>Core: execute_explore_run
  Core->>MS: run_midscene_task(explore payload)
  MS-->>Core: JSONL line/done
  Core-->>Bridge: SSE line/usage（经 Client stream）
  Bridge-->>UI: 轮询 step_log / feature_json
```

#### 测试执行调用链

```mermaid
sequenceDiagram
  participant UI as CasesView
  participant API as test_cases_router
  participant Exec as executor
  participant Client as agent_service_client
  participant FA as func_agent_router
  participant Orch as orchestrator
  participant Graph as FuncDispatchGraph
  participant AG as AutoglmExecGraph
  participant MS as MidsceneExecGraph

  UI->>API: POST /test-cases/{id}/run
  API->>Exec: execute_test_run（线程）
  Exec->>Exec: build_agent_task_text / agent_steps
  Exec->>Client: POST func-agent/dispatch
  Client->>FA: 202 task_id
  Exec->>Client: GET …/dispatch/{id}/stream SSE
  FA->>Orch: run_func_agent_dispatch
  Orch->>Graph: run_func_dispatch_graph
  alt backend autoglm
    Graph->>AG: run_autoglm_graph
    AG-->>FA: SSE step
  else backend midscene
    Graph->>MS: run_midscene_graph
    MS-->>FA: SSE line/usage
  end
  FA-->>Exec: done / error / cancelled
  Exec-->>UI: 轮询 GET /runs/{id}
```

#### LangGraph 节点与 SSE 事件（实现对照）

| 图 | 节点（顺序） | 真机 / 子进程 | agent_service SSE 事件 |
|----|--------------|---------------|-------------------------|
| `ExploreOrchestratorGraph` | `validate_dispatch` → `run_explore` → `sync_tree` | Midscene `explore` JSONL | `line` / `usage` / `done` / `error` |
| `FuncDispatchGraph` | 按 `backend` 分支 | — | — |
| `AutoglmExecGraph` | 步进循环 `PhoneTestAgent` | 同进程 ADB/HDC | `step` |
| `MidsceneExecGraph` | 调 `midscene_dispatch` | Node 子进程 `--web-dispatch` | `line` / `usage` / `done` |

任务生命周期（**四条**长任务共用 agent `task_manager`）：POST 返回 `task_id` → GET `…/stream` 推 SSE → DELETE 取消（杀子进程 / 中断图执行）。Web 侧 `executor` / `feature_analysis_bridge` / **`case_generation_jobs`** 消费 SSE，分别写 `test_runs.step_log`、分析 `step_log`、Job 内存 `step_log`。

#### agent_service HTTP API（Web 消费）

| 能力 | 提交 | 流式 | 取消 |
|------|------|------|------|
| 用例生成 | `POST /api/agent/analysis/generate-case-draft` | `GET …/generate-case-draft/{id}/stream`（`progress` / `done` / `error`） | `DELETE …/generate-case-draft/{id}` |
| 功能点分析 | `POST /api/agent/explore/run` | `GET …/explore/run/{id}/stream` | `DELETE …/explore/run/{id}` |
| 测试执行 | `POST /api/agent/func-agent/dispatch` | `GET …/func-agent/dispatch/{id}/stream` | `DELETE …/func-agent/dispatch/{id}` |
| 健康检查 | `GET /api/agent/health` | — | — |

服务间 KB：`GET /api/internal/knowledge/cases/search`（仅 Web :8000，Bearer `WEB_SERVICE_TOKEN`）。

```mermaid
flowchart LR
  subgraph web["Web :8000"]
    WAPI[FastAPI routers]
    WClient[agent_service_client]
    WKB[case_kb / internal_knowledge]
  end
  subgraph agent["agent_service :8100"]
    Routers[service/routers]
  end
  subgraph lc["langchain_platform"]
    CG[CaseGenChain]
    EG[ExploreOrchestratorGraph]
    FG[FuncDispatchGraph]
  end
  WAPI --> WClient
  WClient -->|HTTP SSE| Routers
  Routers --> CG
  Routers --> EG
  Routers --> FG
  CG -.->|可选| WKB
```

### 1.4 端到端：用例生成 · 功能点分析 · 测试执行

平台里至少涉及**两类业务定位的机器人实例**（均可在商城租用）。**测试分析**实例在同一项目下可承担 **用例生成**（无真机）与 **功能点分析**（须真机）两项能力，二者互斥占用；**测试执行**实例在真机上跑已落库用例，内部再选 AutoGLM 或 Midscene 技术路线。

| 维度 | 测试分析 · 用例生成 | 测试分析 · 功能点分析 | 测试执行 · 设备自动化 |
|------|---------------------|----------------------|------------------------|
| 典型 `catalog_robot_id` | **测试分析**（`test_analysis`） | 同上（同一类实例） | **功能执行**等 |
| LangChain 实现 | `CaseGenChain` | `ExploreOrchestratorGraph` | `FuncDispatchGraph` → AutoGLM / Midscene |
| 对应代码（门面） | `analysis_agent` / `AnalysisAgent` | `feature_explore` / `FeatureExploreAgent` | `func_agent/orchestrator`（`executor` 择路） |
| 是否连真机 | **否** | **是**（ADB/HDC） | **是** |
| 主要 Web 入口 | 测试用例页 → **自动生成** | 项目空间 → **功能点分析** | 测试用例页 → **执行测试** |
| 关键 API | `POST /api/test-cases/generate`、`POST /api/test-cases` | `POST /api/projects/{id}/feature-analysis/runs`、`…/confirm` | `POST /api/test-cases/{id}/run`、`GET …/runs/{id}` |
| 环境变量 | `CASE_GEN_*` | `MIDSCENE_*`、`EXPLORE_TRAVERSE_MODE` 等 | `BIGMODEL_*` / `MIDSCENE_*`、设备 ID |
| 产出物 | `test_cases` | `project_feature_trees`（确认版功能树） | `test_runs`、报告 |

**推荐协作顺序（业务视角）**

1. **准备项目**：在「项目空间」填写被测应用、测试目标等。  
2. **租用并启动测试分析实例**：商城租用「测试分析」→ 审批通过后启动实例。  
3. **（可选）功能点分析**：项目卡片进入「功能点分析」→ 选 App 与遍历参数 → 真机混合遍历 → 编辑功能树 → **确认保存**多版本（取消/失败时若有采集数据也可确认）。  
4. **生成并保存用例**：用例页「自动生成」选同一分析实例 → `generate` 草稿 → 编辑 → **保存** `test_cases`（与步骤 3 **不可同时进行**，实例互斥）。  
5. **租用并启动测试执行实例**：选择 **技术路线**（AutoGLM / Midscene）与默认平台。  
6. **执行与观测**：选用例 → 选执行实例与终端 → `run` → 轮询 / 投屏 → 报告。

```mermaid
flowchart TB
  subgraph gen["用例生成（无真机）"]
    A1[测试分析实例]
    A2[POST /test-cases/generate]
    A3[CaseGenChain + CASE_GEN_*]
    A4[编辑草稿]
    A5[POST /test-cases]
    A1 --> A2 --> A3 --> A4 --> A5
  end

  subgraph fa["功能点分析（真机 · Midscene explore）"]
    F1[测试分析实例]
    F2[POST /feature-analysis/runs]
    F3[feature_analysis_bridge]
    F4[midscene explore 子进程]
    F5[编辑 / POST confirm]
    F6[project_feature_trees]
    F1 --> F2 --> F3 --> F4 --> F5 --> F6
  end

  subgraph run["测试执行（真机）"]
    B1[测试执行实例]
    B2[POST /test-cases/id/run]
    B3[executor → FuncDispatchGraph]
    B4[test_runs]
    B1 --> B2 --> B3 --> B4
  end

  A5 -->|test_cases| B2
  F6 -.->|可选：参考功能树写用例| A2
```

**实现提示**：生成接口校验实例为分析类（`catalog_robot_id` / 目录约定）；执行接口校验实例为执行类且与用例格式、引擎一致。详见 `case_generation.py`、`routers/test_cases.py`、`executor.py`。

## 2. 技术栈总览

### 2.1 按运行时进程

| 进程 | 端口 | 主要技术 | 职责 |
|------|------|----------|------|
| 前端 | 5173 | Vue 3、Vite 6、Pinia、Vue Router、Axios | UI、JWT 存 localStorage、轮询 / SSE 消费由后端代理 |
| Web 后端 | 8000 | FastAPI、Uvicorn、SQLAlchemy 2、Pydantic v2、PyMySQL、**qdrant-client**、OpenAI SDK | 认证、多租户、ORM、**知识库 ingest/query**、编排 agent_service、设备发现/投屏 |
| agent_service | 8100 | FastAPI、Uvicorn、**LangChain 1.x**、LangGraph、OpenAI SDK 2.x | LLM 用例生成、探索/执行编排、SSE 任务、设备执行、**Agentic RAG Tool** |
| Midscene CLI | 子进程 | Node ≥18、`@midscene/android` / `@midscene/harmony` | 视觉 `aiAct`、explore 遍历（由 agent 拉起） |
| MySQL | 3306 | MySQL 8（Docker Compose） | 关系型持久化（含知识库元数据与切片正文） |
| Qdrant | 6333 / 6334 | Qdrant（Docker Compose） | 向量索引与语义检索；Dashboard `http://127.0.0.1:6333/dashboard` |

Web 后端**不**直接 `import` agent 包；仅 HTTP（`agent_service_client.py`）。配置拆分：`web/backend/.env` 与 `agent_service/.env`（无仓库根 `.env`）。

### 2.2 分层技术明细

| 层级 | 技术 | 语言 / 版本要点 |
|------|------|-----------------|
| 前端框架 | Vue 3（Composition API） | JavaScript |
| 前端构建 | Vite 6 | Node |
| 后端框架 | FastAPI | Python 3 |
| ASGI | Uvicorn `standard` | 两服务均使用；agent 启动建议 `log_config=None` |
| ORM | SQLAlchemy 2.x | 仅 Web 后端 |
| 校验 | Pydantic v2 | Web schemas + agent `service/schemas.py` |
| 认证 | JWT（`python-jose`）+ bcrypt | 仅 Web |
| 数据库 | MySQL 8 | `DATABASE_URL` / `TCM_DATABASE_URL` |
| **Agent 编排** | **LangChain Core 1.4.x**、**LangGraph 1.2.x**、**langchain-openai 1.2.x** | 仅 `agent_service` |
| LLM 调用 | `ChatOpenAI`（用例生成）、OpenAI 兼容 SDK 2.x（AutoGLM 等） | `CASE_GEN_*` / `BIGMODEL_*` |
| **Agentic RAG（主）** | Web `app/knowledge/` + LangGraph Tool（`query_knowledge` 等） | MySQL 元数据 + Qdrant 向量；`POST /api/internal/knowledge/query` |
| **KB（兼容）** | Web `case_kb`（MySQL LIKE）+ `WebCaseKbRetriever` | 用例语义检索失败时 LIKE 降级 |
| **向量库** | **Qdrant**（`qdrant-client`） | 集合 `tcm_knowledge_chunks`；Cosine；payload 过滤 `status=active` |
| **Embedding** | DashScope **`text-embedding-v3`**（OpenAI 兼容 HTTP） | `KB_EMBEDDING_*`；Key 回退 `DASHSCOPE_API_KEY` / `MIDSCENE_MODEL_API_KEY` |
| **文档解析** | `python-docx`、`pymupdf`、`openpyxl`、`xlrd`、HTML/CSV/JSON 自研 | 上传 ≤50MB；切片为自研 `_split_by_size`（**不依赖 NLTK**） |
| **RAG 编排** | LangGraph + `skill_profiles` + `robot_instance_bindings` | `RAG_DEFAULT_MODE=agentic`；scope 按机器人绑定集合 |
| 图像 | Pillow | 截图缩放（`DEVICE_SCREEN_*`） |
| 设备 | ADB、HDC | Android / HarmonyOS |
| 视觉自动化 | Midscene.js | TypeScript；`execution_mode`: `natural` / `explore` |
| GUI Grounding | MAI-UI | `mai_ui_tech/` + Web `mai_ui_service.py` |
| 日志 | `dictConfig`、统一 `LOG_*` 环境变量 | `web/backend/app/logging_config.py`、`agent_service/service/logging_config.py` |
| 可选追踪 | LangSmith | `LANGSMITH_API_KEY`、`LANGCHAIN_TRACING_V2`、`LANGCHAIN_PROJECT`（`configure_langsmith()` 于 agent 启动时注入） |

### 2.3 依赖清单

| 包路径 | 文件 | 说明 |
|--------|------|------|
| Web 后端 | `web/backend/requirements.txt` | FastAPI、SQLAlchemy、PyMySQL、httpx、**qdrant-client**、**openai**、**python-docx**、**pymupdf**、**openpyxl**、**xlrd** 等；`llama-index-*` 在依赖中保留，**运行时 ingest/query 使用自研轻量实现**（`qdrant_store.py` + `embeddings.py`） |
| agent_service | `agent_service/requirements.txt` | FastAPI + **LangChain 1.x** + `openai>=2.26` |
| Midscene | `midscene_tech/package.json` | 视觉执行与 explore |
| AutoGLM 资源 | 根目录 `requirements.txt` | 与 autoglm 设备层共用（CLI） |
| Web 前端 | `web/frontend/package.json` | Vue 生态 |

## 3. 目录结构

```
autoglm-phone-test-agent/          # 仓库根目录
├── ARCHITECTURE.md                # 本文档
├── agent_service/analysis_agent/                # 测试分析门面 → langchain_platform
├── agent_service/langchain_platform/            # LangChain 1.x 实现层
│   ├── chains/case_generation.py              #   CaseGenChain（LCEL）
│   ├── graphs/                                #   explore_run、func_dispatch、autoglm_exec、midscene_exec
│   ├── explore_core.py                        #   explore 事件聚合
│   ├── models.py                              #   get_chat_model(case_gen|autoglm)
│   ├── config.py                              #   WEB_*、LangSmith
│   ├── retrievers/web_case_kb.py
│   ├── tools/                                 #   midscene_dispatch、device_autoglm、registry
│   ├── callbacks/sse.py
│   └── README.md
├── agent_service/func_agent/                    # 功能测试门面 → FuncDispatchGraph
│   ├── orchestrator.py
│   ├── core.py
│   └── backends/
│       ├── autoglm_runner.py
│       ├── autoglm/agent.py
│       └── midscene/runtime.py
├── agent_service/service/                       # agent_service Web 服务（独立进程，端口 8100）
│   ├── app.py                                   #   FastAPI、lifespan、HTTP 访问日志中间件
│   ├── logging_config.py                        #   与 Web 后端一致的 LOG_* 配置
│   ├── __main__.py                              #   python -m agent_service.service
│   ├── task_manager.py                          #   内存任务注册表（SSE 推流 + 取消）
│   ├── schemas.py / sse.py / config.py
│   └── routers/                                 #   health / analysis / func_agent / explore / midscene / tree
├── agent_service/common/
│   └── device_resolve.py                        #   设备 ID 解析（消除对 web backend 的循环依赖）
├── agent_service/requirements.txt               # agent_service 依赖
├── autoglm_phone_tech/           # agent_service/func_agent 后端实现 · AutoGLM（Android/ADB + 鸿蒙/HDC）
│   ├── device/device_factory.py
│   ├── device/adb_bridge.py
│   ├── device/hdc_bridge.py
│   └── config/apps_harmonyos.py
├── midscene_tech/                # agent_service/func_agent 后端实现 · Midscene（Android + HarmonyOS）
│   └── src/
│       ├── agent.ts               # MidsceneTestAgent（跨平台）
│       ├── device_runtime.ts      # Android / 鸿蒙设备层
│       ├── platform.ts            # 平台与引擎类型
│       └── cli.ts                 # CLI；--web-dispatch 供 Web 子进程
├── mai_ui_tech/                  # GUI Grounding 技术路线（MAI-UI Python 包）
│   ├── cli.py / grounding.py / config.py
│   └── scripts/
│       ├── serve_grounding_mlx.sh
│       └── run_cli.sh
├── requirements.txt
├── docker-compose.yml             # 本地 MySQL 8 + Qdrant（docker compose up -d mysql qdrant）
└── web/
    ├── frontend/                  # Vue + Vite
    │   ├── src/
    │   │   ├── api/client.js      # Axios，BASE_URL / 代理
    │   │   ├── stores/auth.js     # Token、登录态
    │   │   ├── router/index.js    # 路由与登录守卫
    │   │   └── views/             # Cases / ProjectFeatureAnalysis / RunLive 等
    │   ├── vite.config.js         # dev 代理 /api → 8000
    │   └── package.json
    └── backend/
        ├── app/
        │   ├── main.py            # FastAPI 入口、configure_logging、HTTP 中间件
        │   ├── logging_config.py  # LOG_LEVEL / LOG_FORMAT / LOG_SQL
        │   ├── database.py        # DATABASE_URL、MySQL engine、ensure_schema
        │   ├── models.py          # SQLAlchemy ORM；MySQL 大字段用 LongText（LONGTEXT）
        │   ├── schemas.py         # Pydantic 出入参
        │   ├── deps.py            # get_current_user（JWT）
        │   ├── auth_utils.py      # 密码、JWT
        │   ├── executor.py        # 测试执行：按 test_agent_backend × 平台路由两技术路线
        │   ├── services/
        │   │   ├── case_generation.py   # Web 适配 → HTTP → CaseGenChain；KB 预检索
        │   │   ├── agent_service_client.py  # HTTP/SSE 客户端（:8100）
        │   │   ├── feature_analysis_bridge.py  # Web 适配 → explore SSE
        │   │   ├── case_agent_text.py   # structured → 执行用自然语言（含虚拟键盘提示）
        │   │   ├── case_kb.py           # 用例 KB 扁平检索（RAG 兼容降级）
        │   │   ├── knowledge_document.py # 单文档删除（向量+文件）
        │   │   ├── knowledge_collection.py # 集合删除
        │   │   ├── knowledge_sync.py    # 功能树 confirm → ingest
        │   │   ├── robot_agent_context.py # 机器人 KB scope 解析
        │   │   ├── device_platform.py   # 平台/终端解析（实例默认 + 本次覆盖）
        │   │   ├── device_discovery.py  # adb devices / hdc list targets（3s TTL 缓存）
        │   │   └── device_screen.py     # 投屏：ADB / HDC
        │   ├── knowledge/               # Agentic RAG：ingest / index / query（§4.8）
        │   │   ├── config.py
        │   │   ├── chunk_policy.py      # 环境/项目/文档索引参数合并
        │   │   ├── ingestion/           # parsers, chunkers, upload_types
        │   │   ├── index/               # pipeline, embeddings, qdrant_store
        │   │   └── query/               # knowledge_search, engine
        │   └── routers/
        │       ├── auth.py
        │       ├── test_cases.py
        │       ├── knowledge.py         # 项目知识库 CRUD / 上传 / 检索 / 审核
        │       ├── internal_knowledge.py  # Internal RAG：query / cases/search / agent-context
        │       ├── project_feature_analysis.py  # 项目功能点分析 runs / confirm
        │       ├── robot_instances.py
        │       ├── devices.py           # GET /devices/connected
        │       └── admin.py             # 租用审批 → 实例化 + 引擎/平台
        ├── requirements.txt       # Web 后端依赖（含 pymysql）
        └── data/                  # 上传包、导出文件等（非数据库）
```

## 4. 运行时架构

下图按 **§1.0** 的概念分层：**测试分析**含用例生成（无真机）与**功能点分析**（Midscene explore）；**测试执行**在 AutoGLM / Midscene 用例执行两条路线间二选一。**agent_service 为独立 Web 服务**（端口 8100），web 后端通过 HTTP 调用（`agent_service_client.py`），长任务以 SSE 推流。与 §4.1–§4.6 的端口、HTTP 轮询与 WebSocket 一致。开发环境下浏览器 HTTP 常经 Vite 将 `/api` 代理到 Uvicorn（见 4.1）。

```mermaid
flowchart TB
  subgraph client["客户端"]
    Vue["Vue 3 前端\nCasesView / FeatureAnalysisView"]
  end

  subgraph server["Web 后端（端口 8000）"]
    FastAPI["FastAPI + 路由/服务"]
    Client["agent_service_client.py\nHTTP 客户端"]
    Gen["case_generation.py"]
    FAB["feature_analysis_bridge.py"]
    Exec["executor.py\n用例执行调度"]
    DB[("MySQL_8")]
  end

  subgraph agent["Agent Service（端口 8100 · 独立进程）"]
    ASApp["FastAPI + routers\nSSE 推流 / 任务管理"]
    LC["langchain_platform\nCaseGenChain / LangGraph"]
    AA["AnalysisAgent\n门面"]
    FE["FeatureExploreAgent\n门面"]
    Orch["func_agent/orchestrator"]
    PTA["autoglm_phone_tech\nADB/HDC"]
    MSProc["midscene_tech 子进程"]
    LLMGen["ChatOpenAI\nCASE_GEN_*"]
    LLM1["智谱等"]
    LLMVis["Midscene 视觉模型\nMIDSCENE_*"]
  end

  subgraph future["其他功能定位（扩展）"]
    FX["专项执行 / 质量评估等"]
  end

  Vue --> FastAPI
  FastAPI --> DB
  FastAPI -->|"用例生成"| Gen -->|"HTTP POST"| Client
  FastAPI -->|"功能点分析"| FAB -->|"HTTP SSE"| Client
  FastAPI -->|"用例执行"| Exec -->|"HTTP SSE"| Client
  Client -->|"HTTP"| ASApp
  ASApp --> AA
  AA --> LC
  LC --> LLMGen
  Gen -.->|"可选 internal KB"| Client
  ASApp --> FE
  FE --> LC
  FE --> MSProc
  ASApp --> Orch
  Orch --> LC
  LC --> PTA
  LC --> MSProc
  PTA --> LLM1
  MSProc --> LLMVis
  PTA --> ADB["ADB"]
  PTA --> HDC["HDC"]
  MSProc --> ADB
  MSProc --> HDC
  FastAPI -.-> FX
```

说明：**测试执行**由 **`test_agent_backend`** × **`device_platform`** 在 `executor` 内择路（§1.1）。**功能点分析**不经 `executor`，固定走 `feature_analysis_bridge` → `explore`（§4.6）。**用例生成**不经 `midscene_tech`。同一 `midscene_tech` 包可被「用例执行」与「功能点分析」以不同 `execution_mode` 复用。

### 4.1 进程与端口（典型本地开发）

| 组件 | 默认端口 | 说明 |
|------|-----------|------|
| Vite 开发服务器 | 5173 | 浏览器访问前端 |
| Uvicorn（FastAPI） | 8000 | Web 后端；浏览器通常不直连，`/api` 由 Vite **proxy** 到 8000 |
| Agent Service（FastAPI） | 8100 | agent_service Web 服务；web 后端通过 HTTP 调用，SSE 推流长任务 |
| MySQL 8 | 3306 | `docker compose up -d mysql` |
| Qdrant | 6333（HTTP + Dashboard）、6334（gRPC） | 向量库；**Web UI**：`http://127.0.0.1:6333/dashboard`；集合默认 `tcm_knowledge_chunks` |

前端 Axios 使用 `VITE_API_BASE`（可为空）。开发时常为空，请求走同源 `/api`，由 Vite 转发到后端。

agent_service 由 web 后端通过 `app/services/agent_service_client.py`（HTTP 客户端）调用，不再使用 Python `import`。长任务（测试执行、功能探索）先 POST 提交获取 `task_id`，再 GET SSE stream 接收事件，DELETE 取消。

### 4.2 请求链路（登录后）

1. 浏览器 → `POST /api/auth/login`（或 register）→ 返回 JWT。  
2. 前端 `localStorage` 存 token，后续请求 `Authorization: Bearer ...`。  
3. 用例列表 → `GET /api/test-cases`。
3b. **AI 生成草稿** → `POST /api/test-cases/generate`（**202 + `job_id`**）→ `case_generation_jobs` 后台线程：`case_kb` 预检索 → HTTP `POST /api/agent/analysis/generate-case-draft`（202）+ SSE → `AnalysisAgent` → `CaseGenAgenticGraph` / `CaseGenChain`（§1.3.1）；前端轮询 `GET /api/test-cases/generate/{job_id}`（`step_log`、`draft`）；可选 `DELETE …/generate/{job_id}` 取消。**不写库**直至 `POST /api/test-cases`。须**测试分析**实例；与功能点分析、用例执行**互斥**（见 §1.4）。
3c. **功能点分析** → `POST /api/projects/{id}/feature-analysis/runs`；`feature_analysis_bridge` → HTTP submit/SSE → `FeatureExploreAgent` → `ExploreOrchestratorGraph` → Midscene `explore`；轮询 `GET …/runs/{id}`；结束后 `POST …/confirm` → `project_feature_trees`。详见 §1.3.1、§4.6。
4. 执行 → `POST /api/test-cases/{id}/run`：请求体含 `robot_instance_id`，可选 `device_platform`、`device_id`；创建 `TestRun` 后**异步**在线程池执行 `executor.execute_test_run`。  
5. 执行前枚举设备 → `GET /api/devices/connected?platform=…`（用例页「目标终端」下拉）。  
6. 前端轮询 → `GET /api/test-cases/runs/{run_id}` 获取 `status`、`step_log`、`output_message` 等。

### 4.3 执行链路（测试执行机器人 · 核心）

1. `POST /api/test-cases/{id}/run` 携带 `robot_instance_id`；可选 `device_platform`、`device_id` 覆盖本次执行目标。  
2. 后端合并实例默认与本次参数：`resolve_execution_platform()`、`resolve_execution_device_id()`，写入 `test_runs.device_platform`、`test_runs.device_id`。  
3. 读取实例 `test_agent_backend`（**测试执行**技术路线）。  
4. 路由分支（`executor.py`）：  
   - 构建 dispatch dict → `submit_func_agent_dispatch()` HTTP 提交到 agent_service → 获取 `task_id` → 存入 `_run_task_ids` 映射。  
   - 循环读取 `stream_func_agent_events(task_id)` SSE 流：`step` / `line` / `usage` / `done` / `cancelled` 事件 → 写入 `step_log`。  
   - agent_service：`orchestrator` → **`FuncDispatchGraph`** → `AutoglmExecGraph`（同进程 `autoglm_phone_tech`）或 `MidsceneExecGraph`（`midscene_dispatch` 子进程）。  
5. Midscene 事件：`kind: meta|step|done` → `step_log`；成功可写 `report_path`。  
6. 取消：`signal_cancel(run_id)` 同时设置本地 `threading.Event` + 通过 `_run_task_ids` 查找 `task_id` 直接 HTTP DELETE 到 agent_service，确保 SSE 流立即中断；前端 `POST …/runs/{id}/cancel`。  
7. 投屏：`GET …/device-screen?device_platform=&device_id=`，与用例页当前选择一致（`device_screen.py`）。

### 4.4 WebSocket 运行监控（大屏）

1. 浏览器打开 `/monitor`（仅 `platform_admin` / `tse`），使用 **同源 WebSocket** `ws(s)://…/api/ws/monitor/robots?token=<JWT>`（开发时走 Vite `/api` 代理，`vite.config.js` 需 `ws: true`）。  
2. 后端 `accept` 后校验 JWT 与角色，随后按固定间隔（约 2s）推送 JSON：`online`、`idle`、`executing`；其中 **executing** 与库表 `test_runs` 中 `status=running` 条数一致，**idle** 等可由 `app/services/robot_monitor.py` 占位模拟，对接 Agent 管理服务后改为拉取/订阅同一指标源。  
3. 断线后前端可指数退避重连，用于展示与运营值守场景。

### 4.5 APP 功能清单探索（Midscene，全局）

1. 前端 `/app-explore` → `POST /api/app-explore/runs`（`bundle_id` 与 `hdc shell bm dump -a` 一致；`GET /installed-apps` 拉列表）。  
2. `app_explore_service` 子进程调用 `midscene_tech`：`execution_mode: "explore"`（默认 `traverse_mode=hybrid`，见 §4.6）。  
3. 结果写入 `feature_json` 并导出 Excel；机器人须 `test_agent_backend=midscene`，与同实例用例执行互斥。

### 4.6 项目功能点分析（Midscene + 测试分析实例）

与 §4.5 区分：**绑定项目空间**，走 `project_feature_analysis_runs` / `project_feature_trees`；仅 `catalog_robot_id=test_analysis` 实例；与同实例 **用例生成**、**其它分析任务** 互斥（`feature_analysis_guard` / `analysis_instance_guard`）。

```mermaid
sequenceDiagram
  participant UI as ProjectFeatureAnalysisView
  participant API as project_feature_analysis
  participant Bridge as feature_analysis_bridge
  participant Client as agent_service_client
  participant AS as Agent Service（FE + Midscene）

  UI->>API: POST /runs（traverse_mode, max_screens, …）
  API->>Bridge: 异步 execute_feature_analysis_run
  Bridge->>Client: submit_explore_run → task_id
  Bridge->>Client: stream_explore_events(task_id) SSE
  Client->>AS: HTTP SSE stream
  AS-->>Bridge: explore_page / explore_feature / done 事件
  Bridge-->>API: 增量写 feature_json、step_log
  UI->>API: GET /runs/{id} 轮询
  UI->>API: POST /runs/{id}/confirm（可取消/失败后若有功能点）
  API-->>UI: project_feature_trees 新版本
```

| 项 | 说明 |
|----|------|
| 编排门面 | `analysis_agent/feature_explore/agent.py` → `langchain_platform/graphs/explore_run.py` |
| 核心执行 | `langchain_platform/explore_core.py` → `tools/midscene_dispatch.py` |
| Web 适配 | `web/backend/app/services/feature_analysis_bridge.py` |
| 路由 | `web/backend/app/routers/project_feature_analysis.py` |
| 遍历实现 | `midscene_tech/src/explore.ts`（`explore_common` / `explore_snapshot` / `explore_nav` / `explore_traverse`） |
| 默认策略 | **`hybrid`**：先广度扫 Tab/主导航（`bfs_max_depth` 默认 1），再深入页内；可选 `bfs`、`dfs` |
| 环境默认 | `EXPLORE_TRAVERSE_MODE=hybrid`（可被任务体 `traverse_mode` 覆盖） |

**遍历参数（创建任务 / `ExploreDispatch`）**

| 参数 | 含义 |
|------|------|
| `max_screens` | 最多记录多少个**不同界面**（新页面指纹计 1）；达上限停止探索 |
| `max_depth` | 从应用主界面起，导航路径最多**向下几层**（如 根→Tab→子页→再进一层 = 深度 3） |
| `bfs_max_depth` | hybrid/bfs 下，前几层优先扫 Tab/底栏/侧栏，再点页内按钮 |
| `traverse_mode` | `hybrid`（默认）\| `bfs` \| `dfs` |
| `fair_share_per_root` | `0` 关闭；`-1` 按 `max_screens ÷ 一级 Tab 数` 为每分支分配界面预算；正数为每分支固定上限 |

**确认保存**：`POST …/runs/{run_id}/confirm` 在任务状态为 `success` / `cancelled` / `failed` 且 `feature_json` 含功能点时均可提交；异常中断时 bridge 会尽量 `finalize` 已采集数据。前端工作台可编辑后写入 `project_feature_trees`。

**版本标签（`version_label`）**：请求体可空；默认由 `project_feature_analysis._default_version_label_for_app` 生成 **`{应用展示名或 bundle 末段}-vN`**（`N` 为同项目、同应用下已有 `v*` / `*-v*` 标签的最大序号 +1，兼容历史纯 `v5` 格式）。编辑另存为新版本时 `_next_version_label` 递增（如 `联系人-v5` → `联系人-v6`）。确认后 `knowledge_sync.sync_feature_tree_to_knowledge` 写入 `doc_type=feature_tree`：标题优先用 `version_label`；若仍为纯 `vN` 则展示为 `{应用名}-vN`。

**与顶栏「功能清单探索」**：后者无项目归属、表 `app_explore_runs`；项目内入口为项目卡片「功能点分析」。

### 4.7 可观测性（日志）

两服务均在加载 `.env` 后调用 `configure_logging()`，默认 **detailed** 格式：

`2026-05-27 11:09:24.463 | INFO | agent_service.http | app.py:94 | GET /api/agent/health | client=127.0.0.1 | status=200 | 1.1ms`

| 变量 | Web 后端 | agent_service | 说明 |
|------|----------|---------------|------|
| `LOG_LEVEL` | ✓ | ✓ | 默认 `INFO` |
| `LOG_FORMAT` | ✓ | ✓ | `detailed` \| `simple` \| `custom` |
| `LOG_FORMAT_TEMPLATE` | ✓ | ✓ | `LOG_FORMAT=custom` 时生效 |
| `LOG_HTTP_QUERY` | ✓ | ✓ | 访问日志是否带 query |
| `LOG_HTTP_QUIET_POLLS` | ✓ | ✓ | 健康检查 / SSE stream 降为 DEBUG |
| `LOG_SQL` | ✓ | — | SQLAlchemy SQL（仅 Web） |
| `LOG_HTTP` | — | ✓ | `httpx`/`httpcore` 详情（KB Retriever） |

agent 启动：`python -m agent_service.service`（`access_log=False`，避免与 `agent_service.http` 重复）。

### 4.8 Agentic RAG 知识库：索引、检索与业务流

项目知识库采用 **MySQL 元数据 + Qdrant 向量** 双存储；索引与检索均在 **Web 后端**（`:8000`）完成，agent_service 经 **Internal API** 调用语义检索，LangGraph **Tool**（`query_knowledge` 等）按机器人绑定的集合与 Skill 过滤 scope。

#### 4.8.1 业务定位与页面

| 角色 / 页面 | 路径 | 能力 |
|-------------|------|------|
| 项目成员 | `/projects/:id/knowledge`（`ProjectKnowledgeView.vue`） | 管理**知识集合**；左侧**项目索引设置**；上传（含**高级索引选项**）；文档列表（**索引设置**弹窗、自定义索引标签、重建索引）；**检索测试** |
| 平台管理员 | `/knowledge/review`（`KnowledgeReviewView.vue`） | 审核上传的**测试规范 / 测试策略**（`platform_admin` 专属） |
| 机器人配置 | 我的机器人详情 | 绑定 `knowledge_collections` + `skill_profile`（控制 Agent 可用 Tool 与 RAG scope） |

**业务要点**

- 知识按**项目**隔离；集合用于分组（如「验证集」「功能树分析知识集」）。
- **仅 `status=active` 且向量已写入 Qdrant 的切片**参与语义检索（检索测试、Internal API、Agent Tool 均如此）。
- 上传的 **standard / strategy** 类文档须**平台管理员审核通过**后才写入向量库；其他类型（`page_model`、`glossary`、`execution_hint`、`other` 等）解析后直接发布并索引。**上传时选错文档类型**（如规范 Word 却选「执行经验」）会跳过审核门禁。
- 用例（`doc_type=case`）、功能树（`feature_tree`）可由 DB 同步自动入库，走同一 ingest 流水线。

#### 4.8.2 技术架构

```mermaid
flowchart TB
  subgraph ui["Web 前端"]
    PKV["ProjectKnowledgeView\n集合 / 上传 / 检索测试"]
    KRV["KnowledgeReviewView\n规范审核"]
  end

  subgraph web["Web 后端 app/knowledge/"]
    Router["routers/knowledge.py"]
    Ingest["ingestion/\nparsers · chunkers · upload_types"]
    Pipe["index/pipeline.py\nparse → chunk → embed → Qdrant"]
    Query["query/service.py\nknowledge_search"]
    Emb["index/embeddings.py\nDashScope text-embedding-v3"]
    Qdrant["index/qdrant_store.py"]
  end

  subgraph store["存储"]
    MySQL[("MySQL\nknowledge_* 表")]
    QD[("Qdrant\ntcm_knowledge_chunks")]
    FS["本地文件\nKB_FILE_STORAGE"]
  end

  subgraph agent["agent_service"]
    Tool["langchain_platform/tools\nquery_knowledge 等"]
    Graph["CaseGen / Explore / FuncDispatch Graph"]
  end

  PKV --> Router
  KRV --> Router
  Router --> Ingest --> Pipe
  Pipe --> Emb
  Pipe --> MySQL
  Pipe --> QD
  Pipe --> FS
  Router --> Query
  Query --> Emb
  Query --> QD
  Query --> MySQL
  Graph --> Tool
  Tool -->|"POST /api/internal/knowledge/query\nBearer WEB_SERVICE_TOKEN"| Query
```

| 层次 | 路径 | 说明 |
|------|------|------|
| 配置 | `app/knowledge/config.py` | `QDRANT_*`、`KB_EMBEDDING_*`、`KB_FILE_STORAGE`、`KB_SEARCH_MIN_SCORE`、`RAG_DEFAULT_MODE` |
| 切片策略 | `app/knowledge/chunk_policy.py` | 环境 → 项目 `chunk_policy_json` → 文档 `chunk_policy_json` 合并；`effective_search_min_score` |
| 解析 | `app/knowledge/ingestion/parsers.py` | TXT/MD/PDF/DOCX/XLSX/HTML/JSON 等；DOCX 含段落 + 表格 |
| 切片 | `app/knowledge/ingestion/chunkers.py` | 按 `doc_type` + `heading_aware`：规范类按章节标题切分；`build_embed_text` 加【文档】【章节】前缀 |
| 索引 | `app/knowledge/index/pipeline.py` | 异步 `ThreadPoolExecutor`；`schedule_ingest(document_id)` |
| 向量 | `app/knowledge/index/embeddings.py` | OpenAI 兼容 HTTP → DashScope `text-embedding-v3` |
| 检索 | `app/knowledge/query/service.py` | query embedding → Qdrant 过滤检索 → MySQL 取 snippet |
| 服务 | `app/services/knowledge_document.py` | 单文档删除（Qdrant + 文件 + ORM） |
| 服务 | `app/services/knowledge_collection.py` | 集合删除（级联文档与向量） |
| Internal | `app/routers/internal_knowledge.py` | agent 专用；Bearer `WEB_SERVICE_TOKEN` |

#### 4.8.3 文档状态机（业务处理）

```
上传/录入 → pending_parse → parsing → …
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
   pending_review          active               draft
 （规范/策略待审）      （已发布可检索）      （解析失败/空内容）
         │                    │
    驳回 rejected        重建索引 / 删除
         │
    修改后 submit-review → pending_review
```

| 状态 | 含义 | 是否参与检索 |
|------|------|--------------|
| `pending_parse` | 已创建，等待后台 ingest | 否 |
| `parsing` | 索引任务进行中 | 否 |
| `pending_review` | 已解析切片，等待平台管理员审核（**standard/strategy 上传**） | 否（仅 MySQL 有文本，Qdrant 无向量） |
| `active` | 已发布；向量索引完成（或无需审核的类型） | **是** |
| `draft` | 解析失败或内容为空 | 否 |
| `rejected` | 审核驳回 | 否 |
| `archived` | 已归档 | 否 |

**审核门禁（standard / strategy + upload）**

1. 首次 ingest：`was_published=False` → 只 **parse + chunk**，chunk 标记 `embedding_status=parsed`，文档 → `pending_review`。
2. 平台管理员 `POST /api/knowledge/documents/{id}/review`（`approve=true`）→ `status=active` → 再次 `schedule_ingest`。
3. 二次 ingest：`was_published=True` → **embed + upsert Qdrant**，文档保持 `active`。

非规范类（如 `page_model`、`glossary`、`execution_hint`、`other`）首次 ingest 即 embed 并置 `active`。

**审核判定代码**（`pipeline.py`）：`_upload_requires_review(doc)` ⇔ `doc.source_type == "upload"` 且 `doc.doc_type in {"standard", "strategy"}`。

#### 4.8.4 索引流水线（技术处理）

`run_ingest_document(db, document_id)`（`pipeline.py`）步骤：

1. **门禁**：`pending_review` / `rejected` / `archived` 不跑；`parsing` 超过 2 分钟视为僵死任务可重跑。
2. **解析**：`parse_document_content()` — 文件路径或 `structured_json`；用例/功能树走 DB 同步源。
3. **清旧索引**：删除旧 `knowledge_chunks` 及对应 Qdrant point。
4. **切片**：`resolve_chunk_policy(db, project_id, document_id)` 取有效参数 → `chunk_text(...)` → `(section_path, content)`；`build_embed_text()` 拼接标题前缀后 `_embed_text()`。
5. **向量化**（当 `indexable=True`）：DashScope embedding → `upsert_point`；payload 含 `chunk_id`、`document_id`、`collection_id`、`project_id`、`doc_type`、`status=active`。
6. **落库**：chunk 的 `embedding_status` 为 `indexed` | `parsed` | `failed`。
7. **异常**：任一步骤未捕获异常 → 回滚并置 `pending_parse`；避免永久卡在 `parsing`。

触发 ingest 的入口：上传/结构化录入、`reindex`、审核通过、用例保存同步（`sync_case_document`）、功能树确认（`knowledge_sync`）。

#### 4.8.5 检索流水线

**浏览器检索测试**：`GET /api/knowledge/projects/{project_id}/search?q=…&collection_id=…`

**Agent 主入口**：`POST /api/internal/knowledge/query`（body 含 `robot_instance_id` 时按 `robot_instance_bindings` 限定 `collection_ids` 与 `rag_policy`）

**兼容用例 KB**：`GET /api/internal/knowledge/cases/search` — 先对 `doc_type=case` 做语义检索，无结果时降级 `case_kb` MySQL LIKE。

检索步骤（`knowledge_search`）：

1. 对 query 做 embedding（与索引同一模型）。
2. Qdrant `query_points`，过滤 `status=active`，`score_threshold=effective_search_min_score(project_policy)`，可选 `collection_id` / `project_id` / `doc_type`。
3. 用 payload 中 `chunk_id` 回表 `knowledge_chunks` 取正文 snippet（前 600 字）；响应含 `min_score` 供前端展示。

#### 4.8.6 Agentic RAG 接入（三条业务链）

| 业务链 | 预取 / Tool | 说明 |
|--------|-------------|------|
| 用例生成 | `CaseGenAgenticGraph` + `query_knowledge` | Web `case_generation.py` 传 `robot_instance_id`；`rag_trace` 可观测 |
| 功能点分析 | `ExploreOrchestratorGraph.prefetch_kb_context` | 功能树 confirm → `knowledge_sync`（`version_label` / 应用名标题）→ ingest |
| 测试执行 | `FuncDispatchGraph` prefetch + Recovery RAG | `executor` payload 含 `project_id` / `kb_context` |

机器人 scope：`GET /api/internal/robots/{id}/agent-context` 返回绑定的集合 ID、Skill、`rag_policy` 合并结果。

默认 `RAG_DEFAULT_MODE=agentic`；`skill_profiles` 按 `catalog_robot_id` 配置可用 Tool 列表。

#### 4.8.7 主要 API（用户 JWT）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST/PATCH/DELETE | `/api/knowledge/projects/{id}/collections` | 集合 CRUD |
| GET | `/api/knowledge/projects/{id}/documents` | 文档列表（可按集合、类型筛选） |
| POST | `…/documents/upload` | multipart 上传（≤50MB）；Form：`use_project_chunk_policy`、`chunk_policy_json`（文档级覆盖） |
| POST | `…/documents/structured` | 结构化 JSON 录入；Body 可选 `use_project_chunk_policy` / `chunk_policy` |
| GET/PATCH/DELETE | `…/projects/{id}/chunk-policy` | 项目级索引默认（含 `search_min_score`） |
| GET/PATCH | `…/documents/{doc_id}/chunk-policy` | 文档级切片覆盖；PATCH 支持 `?reindex=true` |
| POST | `…/documents/{doc_id}/submit-review` | 草稿/驳回 → 待审核 |
| DELETE | `…/documents/{doc_id}` | 删除文档 + 向量 + 文件 |
| POST | `/api/knowledge/documents/{doc_id}/reindex` | 排队重建索引（`active` / `draft` / `pending_parse`） |
| GET | `/api/knowledge/projects/{id}/search` | 项目内检索测试 |
| GET | `/api/knowledge/review-queue` | 待审核队列（`platform_admin`） |
| POST | `/api/knowledge/documents/{doc_id}/review` | 审核通过/驳回 |
| PATCH | `/api/knowledge/robot-instances/{id}/knowledge-binding` | 机器人 KB + Skill 绑定 |

#### 4.8.8 环境变量（Web `web/backend/.env`）

| 变量 | 默认 / 说明 |
|------|-------------|
| `QDRANT_URL` | `http://127.0.0.1:6333` |
| `QDRANT_COLLECTION` | `tcm_knowledge_chunks` |
| `KB_EMBEDDING_API_KEY` | 回退 `MIDSCENE_MODEL_API_KEY` / `DASHSCOPE_API_KEY` |
| `KB_EMBEDDING_BASE_URL` | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `KB_EMBEDDING_MODEL` | `text-embedding-v3` |
| `KB_FILE_STORAGE` | `web/backend/data/knowledge` |
| `KB_INGEST_WORKERS` | 索引线程池（实现为 pipeline 内 `max_workers=2`） |
| `KB_SEARCH_MIN_SCORE` | 语义检索最低相似度（余弦 0~1），默认 `0.6`；`0` 关闭；项目页可覆盖 |
| `KB_CHUNK_MAX_CHARS` / `KB_CHUNK_OVERLAP` / `KB_CHUNK_OVERLAP_SHORT` | 切片默认（项目/文档页可覆盖） |
| `KB_CHUNK_PREFIX_TITLE` / `KB_CHUNK_PREFIX_SECTION` / `KB_CHUNK_HEADING_AWARE` | `1`/`0`；是否加前缀、按章节切片 |
| `RAG_DEFAULT_MODE` | `agentic` |
| `WEB_SERVICE_TOKEN` | 与 agent_service 相同，供 Internal API |

#### 4.8.9 索引参数（环境 / 项目 / 文档）

```text
KB_CHUNK_* / KB_SEARCH_MIN_SCORE (.env)
        ↓
project_knowledge_settings.chunk_policy_json   ← 知识库页左侧「索引设置」
        ↓
knowledge_documents.chunk_policy_json        ← 上传「高级索引选项」或文档「索引设置」
        ↓
run_ingest_document → chunk_text + build_embed_text → Qdrant
```

| 字段 | 项目级 | 文档级 |
|------|--------|--------|
| `max_chars` / `overlap` / `overlap_short` | ✓ | ✓ |
| `prefix_title` / `prefix_section` / `heading_aware` | ✓ | ✓ |
| `search_min_score` | ✓（检索阈值） | ✗（始终用项目/环境） |

实现：`app/knowledge/chunk_policy.py`（`normalize_chunk_policy`、`normalize_document_chunk_policy`、`resolve_chunk_policy`）。审核通过后再 `schedule_ingest` 时须在 **`db.commit()` 之后**调度，避免后台线程仍读到 `pending_review`（见 `routers/knowledge.py` `review_document`）。

#### 4.8.10 排查清单

| 现象 | 可能原因 | 处理 |
|------|----------|------|
| 一直「索引中」 | ingest 异常未回滚（已修复 NLTK/异常处理） | 等 2 分钟后刷新或点「重建索引」 |
| 检索结果与文档不符 | 规范类未审核，或审核后未 embed（已修复 `was_published` 逻辑） | 后台 **知识库审核** 通过；文档列表 **重建索引** |
| 检索无结果 | 阈值过高（`KB_SEARCH_MIN_SCORE` / 项目索引设置）、仅少量 active 文档、embedding 失败 | 调低项目「最低相似度」（如 0.55～0.58）后重试；查 Qdrant / `embedding_status` |
| 未走审核直接已发布 | 上传时 `doc_type` 非 standard/strategy | 规范类文档上传时选「测试规范」或「测试策略」 |
| Embedding 400 `Arrearage` | DashScope / 百炼账户欠费停服 | 充值阿里云或更换有效 `KB_EMBEDDING_API_KEY`；重启后端后对文档 **重建索引** |
| Agent 未用到 KB | 机器人未绑定集合 / Skill 未含 `query_knowledge` | 我的机器人 → KB 绑定 |

## 5. 数据存储

- **数据库（MySQL 8）**  
  - 环境变量 **`DATABASE_URL`** 或 **`TCM_DATABASE_URL`**，例如 `mysql+pymysql://user:pass@host:3306/tcm?charset=utf8mb4`。驱动 **PyMySQL**（见 `web/backend/requirements.txt`）。连接池：`TCM_DB_POOL_SIZE`（默认 10）、`TCM_DB_MAX_OVERFLOW`（默认 20）。本地实例：仓库根 **`docker-compose.yml`** → `docker compose up -d mysql`（默认库/用户/密码均为 `tcm`）。  
  - **大字段**：`models.py` 中 `LongText = Text().with_variant(LONGTEXT, "mysql")`，用于 `step_log`、`feature_json` 等。  
  - **启动与健康**：`main.py` 启动时 `create_all` + `ensure_schema()`；`GET /api/health` 执行 `SELECT 1` 并返回 `database: mysql`。  
  - 连接使用 `pool_pre_ping`、`pool_recycle` 与 session `time_zone=+00:00`。  
  - **外部连接（CLI / GUI）**：本地 MySQL 在 Docker 中，映射 **`127.0.0.1:3306`**。须指定 `-h 127.0.0.1`，勿用默认 socket（否则会报 `/tmp/mysql.sock`）。应用账号 `tcm`/`tcm`，库 `tcm`；root 为 `root`/`root`（见 `docker-compose.yml`）。示例：`mysql -h 127.0.0.1 -P 3306 -u tcm -ptcm tcm`；或 `docker compose exec mysql mysql -u tcm -ptcm tcm`。

- **向量库（Qdrant）**  
  - 本地：`docker compose up -d qdrant`（`docker-compose.yml`）。数据卷 `tcm_qdrant_data`。  
  - **Web 管理界面**：**http://127.0.0.1:6333/dashboard**（浏览器打开，可浏览集合、点、payload）。REST 根路径 `http://127.0.0.1:6333/` 用于健康检查。  
  - 应用配置（`web/backend/.env`）：`QDRANT_URL`（默认 `http://127.0.0.1:6333`）、`QDRANT_COLLECTION`（默认 `tcm_knowledge_chunks`）。索引与检索实现见 `web/backend/app/knowledge/index/qdrant_store.py`。  
  - 元数据（文档、集合、切片正文）在 **MySQL**；向量与检索过滤字段（`chunk_id`、`doc_type`、`status` 等）在 **Qdrant**。

- **表（逻辑）**  
  - `users`：账号与密码哈希、RBAC `role` 等。  
  - `projects`：项目空间（被测应用、测试目标），多租户按 `owner_id`。  
  - `test_cases`：归属 `project_id`；标题、执行说明、前置条件、`steps_json`（步骤与预期）、`task_text`、`priority`、`revision_no`。  
  - `test_case_revisions`：每次保存的快照（版本管理）。  
  - `case_kb_documents`：检索用扁平文本（标题/步骤/说明聚合），供 `/api/knowledge/cases/search` 与 RAG（**兼容降级路径**）。
  - `knowledge_collections`：项目知识集合（名称、描述、归属项目）。
  - `knowledge_documents`：知识文档（类型、来源、状态、文件路径、审核字段、`chunk_policy_json` 文档级切片覆盖）；`status` 见 §4.8.3。
  - `knowledge_chunks`：切片正文 + `qdrant_point_id` + `embedding_status`（`indexed` / `parsed` / `failed`）。
  - `project_knowledge_settings`：项目级 `rag_policy_json` + `chunk_policy_json`（索引默认与检索阈值）。
  - `skill_profiles`：按 `catalog_robot_id` 的 Skill 模板（可用 Tool 列表）。
  - `robot_instance_bindings`：实例绑定的 `knowledge_collection_ids` + `skill_profile_id` + RAG 覆盖策略。  
  - `robot_instances`：租用实例化后的数字机器人；`instance_code`（DR-xxxxxx）、`test_agent_backend`、`device_platform`（**默认**平台）、`catalog_robot_id` 等。  
  - `test_runs`：`robot_instance_id`、`device_platform` / `device_id`（**本次**执行实际使用）、`pending` / `running` / `success` / `failed` / `cancelled`、`step_log`、`report_path`（Midscene HTML）、`output_message`、`error_trace`。  
  - `project_reports`：项目维度测试报告摘要（供看板「最新报告」）。  
  - `defects`：缺陷（开放/已解决时间），供看板「未处理缺陷存量」趋势。  
  - `billing_preorders`：机器人商城「立即租用」生成的预订单（`pending_payment` 等），对接支付网关前由计费模块写入。  
  - `project_app_artifacts`：项目内上传的安装包路径；`test_case_sets` / `test_case_set_items`：用例集合；`functional_dispatch_tasks`：功能测试下发任务及 Kafka 投递状态快照。
  - `app_explore_runs`：顶栏「功能清单探索」（全局，与项目无关）。
  - `project_feature_analysis_runs`：项目内功能点分析任务（`traverse_mode`、`max_screens`、`max_depth`、`fair_share_per_root`、`feature_json`、`step_log` 等）。
  - `project_feature_trees`：用户确认后的功能树多版本（`tree_json`、`version_label` 默认 `{app}-vN`、`confirmed_at`）；确认后同步知识库 `feature_tree` 文档。
  - **用例生成 Job（内存）**：`case_generation_jobs` 模块内 `_jobs` 字典（非 MySQL 表），TTL 约 1h；字段含 `status`、`progress_message`、`step_log`、`draft`。

## 6. 外部依赖与环境变量

配置已按服务拆分，不再使用仓库根目录 `.env`：

| 配置文件 | 服务 | 加载方式 |
|----------|------|----------|
| `web/backend/.env` | Web 后端 | `main.py` → `load_dotenv` |
| `agent_service/.env` | Agent Service | `service/app.py` → `load_dotenv` |
| `.env.example`（仓库根目录） | 参考文档 | 唯一环境变量模板；按分区复制到 `web/backend/.env` 与 `agent_service/.env` |

### Web 后端（`web/backend/.env`）

| 变量（示例） | 用途 |
|----------------|------|
| `DATABASE_URL` / `TCM_DATABASE_URL` | MySQL 8 连接字符串 |
| `TCM_DB_POOL_SIZE` / `TCM_DB_MAX_OVERFLOW` | MySQL 连接池（可选） |
| `JWT_SECRET` / `JWT_EXPIRE_MINUTES` | JWT 签名密钥与过期时间 |
| `LOG_LEVEL` / `LOG_FORMAT` / `LOG_HTTP_*` / `LOG_SQL` | 日志（见 §4.7） |
| `TCM_BUILTIN_ADMIN_*` / `TCM_BOOTSTRAP_ADMIN_*` | 内置平台管理员引导 |
| `AGENT_SERVICE_URL` | agent_service 地址（默认 `http://127.0.0.1:8100`） |
| `WEB_SERVICE_TOKEN` | agent_service 调 internal KB API 的 Bearer token（与 agent_service `.env` 相同） |
| `ADB_DEVICE_ID` / `HDC_DEVICE_ID` / `HDC_HOME` | 设备发现与投屏 |
| `DEVICE_SCREEN_MAX_WIDTH` | 投屏缩略图最大宽度 |
| `KAFKA_*` | 功能测试下发（可选） |
| `TCM_APP_UPLOAD_DIR` / `TCM_APP_UPLOAD_MAX_MB` | App 安装包上传 |
| `QDRANT_URL` / `QDRANT_COLLECTION` | Qdrant 向量库（§4.8、§5） |
| `KB_EMBEDDING_API_KEY` / `KB_EMBEDDING_BASE_URL` / `KB_EMBEDDING_MODEL` | 知识库 embedding（DashScope 兼容模式） |
| `KB_FILE_STORAGE` | 知识库上传文件目录 |
| `KB_SEARCH_MIN_SCORE` / `KB_CHUNK_*` | 切片与检索阈值默认（项目页可覆盖） |
| `RAG_DEFAULT_MODE` | `agentic`（默认）或 passive 兼容模式 |

### Agent Service（`agent_service/.env`）

| 变量（示例） | 用途 |
|----------------|------|
| `AGENT_SERVICE_HOST` / `AGENT_SERVICE_PORT` | 监听地址（默认 `0.0.0.0:8100`） |
| `LOG_LEVEL` / `LOG_FORMAT` / `LOG_HTTP_*` | 日志格式与 HTTP 访问日志（与 Web 后端一致，见 `service/logging_config.py`） |
| `BIGMODEL_API_KEY` / `ZHIPU_API_KEY` | 智谱 API Key（AutoGLM + 用例生成兜底） |
| `OPENAI_BASE_URL` | 智谱网关等 |
| `PHONE_AGENT_MODEL` / `PHONE_AGENT_MAX_STEPS` | AutoGLM 模型与步数上限 |
| `CASE_GEN_API_KEY` | 用例生成 API Key；未设则回退 `BIGMODEL_API_KEY` |
| `CASE_GEN_BASE_URL` | 用例生成网关（如 `https://api.deepseek.com`） |
| `CASE_GEN_MODEL` / `CASE_GEN_TIMEOUT_SEC` | 用例生成模型与超时 |
| `CASE_GEN_USE_KB` / `CASE_GEN_KB_LIMIT` | 用例生成是否用 KB、条数上限 |
| `WEB_INTERNAL_API_URL` | Retriever 访问 Web 的 base URL（默认 `http://127.0.0.1:8000`） |
| `WEB_SERVICE_TOKEN` | 与 Web 后端相同；供 `WebCaseKbRetriever` 调 `/api/internal/knowledge/cases/search` |
| `MIDSCENE_MODEL_BASE_URL` / `MIDSCENE_MODEL_API_KEY` | Midscene 视觉模型 |
| `MIDSCENE_MODEL_NAME` / `MIDSCENE_MODEL_FAMILY` | Midscene 模型名与系列 |
| `MIDSCENE_REPLANNING_CYCLE_LIMIT` | 单步 aiAct 重规划上限（默认 100，agent_service 启动时注入） |
| `MIDSCENE_STEP_TIMEOUT_SEC` | 单步 aiAct/aiQuery 超时秒数（默认 180，由 agent_service 注入） |
| `MIDSCENE_EXPLORE_STEP_TIMEOUT_SEC` | 功能遍历单步超时（未设 `MIDSCENE_STEP_TIMEOUT_SEC` 时生效，默认 120） |
| `EXPLORE_TRAVERSE_MODE` | 功能遍历默认策略 |
| `PHONE_AGENT_TIMEOUT_SEC` | AutoGLM 单次模型调用超时（默认 120，`model/client.py`） |
| `DEVICE_SCREEN_MAX_WIDTH` | 截图缩放最大宽度（默认 720，`adb_bridge` / `hdc_bridge`） |
| `DEVICE_SCREEN_JPEG_QUALITY` | 截图 JPEG 质量（默认 75，`adb_bridge` / `hdc_bridge`） |
| `ADB_DEVICE_ID` / `HDC_DEVICE_ID` / `HDC_HOME` | 设备连接（执行用） |
| `LANGSMITH_API_KEY` | LangSmith API Key（与 `LANGCHAIN_API_KEY` 二选一） |
| `LANGCHAIN_TRACING_V2` / `LANGSMITH_TRACING` | 设为 `false` 可关闭；仅配 Key 时默认开启 |
| `LANGCHAIN_PROJECT` / `LANGSMITH_PROJECT` | 追踪项目名，默认 `test-robots` |
| `LANGCHAIN_ENDPOINT` / `LANGSMITH_ENDPOINT` | 可选，默认 LangSmith SaaS |

设备要求：

- **AutoGLM + Android**：USB 调试、ADB、设备上 [ADB Keyboard](https://github.com/senzhk/ADBKeyBoard)（文本输入）。
- **AutoGLM + 鸿蒙**：HDC、`hdc list targets` 可见设备；使用 `uitest` 原生输入（无需 ADB Keyboard）。
- **Midscene**：见 [`midscene_tech/README.md`](./midscene_tech/README.md)。

详见 [`autoglm_phone_tech/README.md`](./autoglm_phone_tech/README.md)。

## 7. 初级工程师维护清单

0. **业务功能或模块职责变更**：同步更新仓库根目录 **README.md**（模块介绍与启动方式）；本文档负责架构级细节与深度链路说明。  
1. **改前端**：只动 `web/frontend`，`npm install` 后 `npm run dev`；接口路径以 `/api` 开头。  
2. **改后端**：`web/backend`，建议使用虚拟环境，`pip install -r requirements.txt`，ASGI 入口为 `app.main:app`。  
3. **改测试执行 · AutoGLM 路线**：`autoglm_phone_tech/`（`device_factory`、`hdc_bridge` 等）；影响所有 `test_agent_backend=autoglm` 的执行。  
4. **改测试执行 · Midscene 路线**：`midscene_tech/`；`npm run typecheck`；影响 `test_agent_backend=midscene`；改完后重启 Uvicorn。长时间任务不建议 `uvicorn --reload`。  
5. **改测试执行路由**：`executor.py`、`services/device_platform.py`；实例字段见 `models.RobotInstance`。  
6. **改 LangChain 编排**：`agent_service/langchain_platform/`（链/图/Retriever/Tool）；门面 `analysis_agent/`、`func_agent/orchestrator.py`；HTTP 路由 `agent_service/service/routers/`。**改代码或 `agent_service/.env` 后须重启 agent_service**（默认无 `--reload`）。  
7. **改测试分析业务类型**：同上 + `web/backend/app/services/case_generation.py`、`feature_analysis_bridge.py`。  
8. **数据库**：MySQL 8；`DATABASE_URL` 必填；无 Alembic，列迁移在 `database.ensure_schema()`。  
9. **排查执行失败**：确认实例 **技术路线（autoglm/midscene）**、用例页 **平台+终端**；`adb devices` / `hdc list targets`；看 agent 日志 `agent_service.func_agent` 与 `step_log`；Midscene 报告见 `report_path`。  
10. **排查 AI 生成失败**：`CASE_GEN_*`、`WEB_SERVICE_TOKEN`（Retriever）；Web `POST /api/test-cases/generate` → 轮询 `GET …/generate/{job_id}` 看 `step_log` / `detail`；agent `GET …/generate-case-draft/{task_id}` 与 SSE；确认 agent_service 可达且未 120s 网关超时（Web 已异步，长任务在 Job + SSE）。`CaseGenChain` 对非法 JSON 自动重试一轮。  
11. **排查知识库索引/检索**：§4.8.10；确认 Qdrant、`KB_EMBEDDING_*`、索引参数 §4.8.9；文档 `status=active` 且 chunk `indexed`；规范类须 **知识库审核** 通过后再检索。

## 8. 一句话小结

**Vue 3 + Web FastAPI + agent_service（LangChain 1.x）+ MySQL 8 + Qdrant**：Web 管租户、知识库 ingest/query 与持久化，agent 管 LLM/图编排与设备执行（HTTP+SSE）。**测试分析**走 `CaseGenChain` / `ExploreOrchestratorGraph`；**测试执行**走 `FuncDispatchGraph`（AutoGLM 同进程或 Midscene 子进程）。用例仅 **structured**；**Agentic RAG** 经 Internal API + Tool 注入三条业务链。详见 §1.3.1、§4.8、§2、§4.7。
