# 测试用例管理平台 — 架构说明（维护向）

本文档描述本仓库的技术架构与目录约定，供初级工程师维护代码时查阅。

## 1. 系统定位

### 1.0 数字机器人 × Agent 边界（概念与扩展）

Web 将租用的**数字机器人实例**按商城 **功能定位（`catalog_robot_id` 等）** 区分能力；**FastAPI 按实例类型把请求路由到不同的 Agent 实现**。与本仓库源码直接对应的归类如下：

| 业务定位（示例） | 代码侧 Agent | 说明 |
|------------------|--------------|------|
| **测试分析机器人** | `agent_service/analysis_agent/` | **用例生成**：LLM → structured/YAML（`CASE_GEN_*`，**不连真机**）。**功能点分析**：真机界面遍历 → GIIC 功能树（`feature_explore/` → Midscene `explore`，`MIDSCENE_*`） |
| **测试执行机器人（func_agent）** | `agent_service/func_agent/`（内含 `autoglm_phone_tech/` 与 `midscene_tech/` 技术后端） | **同一业务定位下的两条技术路线**：LLM 驱动 UI（智谱 AutoGLM-Phone）与视觉驱动 UI（Midscene.js）。由实例字段 **`test_agent_backend`**（`autoglm` \| `midscene`）与 **`device_platform`** 在 `executor.py` 中择路；均经 ADB/HDC 操作真机 |
| **其他功能定位**（专项执行、质量评估等） | 未来各自 **独立 Agent 包 + 路由/服务** | 与 `case_generation`、`executor` 平行扩展；本架构图以虚线占位，不展开具体实现 |

**要点**：`autoglm_phone_tech` 与 `midscene_tech` 在业务上统一归属 **`agent_service/func_agent`（功能测试机器人）**，不是与「测试分析」并列的第三、第四种「机器人类型」；后续若增加新的测试执行技术路线，仍在 `agent_service/func_agent` 域内扩展并由 `executor` 分支选择。

本仓库还包含：

1. **`agent_service/analysis_agent/`（Python）** — **测试分析机器人 Agent**：**用例生成**（`AnalysisAgent`，无真机，Web 适配 `case_generation.py`）；**功能点分析**（`FeatureExploreAgent`，Midscene explore 子进程，Web 适配 `feature_analysis_bridge.py`）。详见 [`agent_service/analysis_agent/README.md`](./agent_service/analysis_agent/README.md)。

2. **`agent_service/func_agent/`（Python）** — **功能测试机器人统一业务域**：向 `executor` 暴露统一调度入口；内部编排两条后端路线（AutoGLM / Midscene）。

3. **`autoglm_phone_tech/`（Python）** 与 **`midscene_tech/`（Node）** — **func_agent 技术后端实现**：前者为观察→推理→执行（ADB/HDC），后者为视觉自动化（`@midscene/android` / `@midscene/harmony`，Web 子进程 `--web-dispatch`）。

4. **`web/`（Web 应用）**  
   **前端**：项目与用例 CRUD、自动生成草稿、触发执行、轮询步骤日志与结果。  
   **后端**：认证与持久化；**用例生成**走 `case_generation` → `analysis_agent`；**功能点分析**走 `feature_analysis_bridge` → `feature_explore` → Midscene explore；**测试执行**走 `executor` → AutoGLM 同进程或 Midscene 子进程。

5. **`mai_ui_tech/`（Python）** — **GUI Grounding 技术路线**：本地 MAI-UI 推理与坐标解析；由 Web 服务 `mai_ui_service.py` 对接 `/api/mai-ui/*` 能力。

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

**用例生成**与 §1.1 **测试执行** 分离：生成路径不调用 `PhoneTestAgent`；LLM 在 Web 进程内通过 OpenAI 兼容 API 产出 **structured** 字段。

**功能点遍历**（`analysis_agent/feature_explore/` → `FeatureExploreAgent`）走 Midscene `explore` 子进程，与用例生成、同实例其它占用互斥；详见 §4.6。

| 项 | 说明 |
|----|------|
| 包 | `agent_service/analysis_agent/`（`AnalysisAgent`，对齐 `autoglm_phone_tech` 目录约定） |
| Web 适配 | `app/services/case_generation.py`（KB 检索 + ORM → `ProjectContext`） |
| 生成路由 | `POST /api/test-cases/generate`（`TestCaseGenerateIn` → `TestCaseGenerateOut`） |
| 持久化 | 上述接口**不写库**；用户在前端编辑后 `POST /api/test-cases` 保存 |
| LLM 输出 | 始终结构化（标题、前置条件、步骤 JSON、执行说明、优先级） |
| 上下文 | `Project.name`、`tested_app_name`、`test_objective` + 用户 `prompt`（用户描述优先于项目被测应用名） |
| RAG | `CASE_GEN_USE_KB=true` 时调用 `case_kb.search_cases_kb`（同项目、同租户 scope） |
| 执行衔接 | structured → `case_agent_text.build_agent_task_text()`（AutoGLM / Midscene natural） |

**注意**：用例已统一为结构化格式（不再支持 YAML）。所有用例通过 `steps_json` + `task_text` 描述步骤，Midscene 执行使用 natural 模式自动转换。`case_format_convert.py` 与 `case_yaml.py` 已移除。

```mermaid
sequenceDiagram
  participant UI as CasesView
  participant API as test_cases_router
  participant Gen as case_generation
  participant AA as analysis_agent
  participant LLM as OpenAI_compatible_API

  UI->>API: POST /generate project_id prompt
  API->>Gen: generate_case_draft
  Gen->>AA: generate_case_draft
  AA->>LLM: chat.completions JSON
  LLM-->>AA: structured draft
  AA-->>Gen: CaseDraft
  Gen-->>API: TestCaseGenerateOut
  API-->>UI: 预填编辑弹窗
  UI->>API: POST /test-cases 保存
```

**配置**：仓库根 `.env` 的 `CASE_GEN_*`。本地调试常用 DeepSeek（`CASE_GEN_BASE_URL=https://api.deepseek.com`、`CASE_GEN_MODEL=deepseek-v4-pro`）；未设 `CASE_GEN_API_KEY` 时回退 `BIGMODEL_API_KEY`。详见 §6 环境变量表。

### 1.4 端到端：用例生成 · 功能点分析 · 测试执行

平台里至少涉及**两类业务定位的机器人实例**（均可在商城租用）。**测试分析**实例在同一项目下可承担 **用例生成**（无真机）与 **功能点分析**（须真机）两项能力，二者互斥占用；**测试执行**实例在真机上跑已落库用例，内部再选 AutoGLM 或 Midscene 技术路线。

| 维度 | 测试分析 · 用例生成 | 测试分析 · 功能点分析 | 测试执行 · 设备自动化 |
|------|---------------------|----------------------|------------------------|
| 典型 `catalog_robot_id` | **测试分析**（`test_analysis`） | 同上（同一类实例） | **功能执行**等 |
| 对应代码 | `analysis_agent` / `AnalysisAgent` | `analysis_agent/feature_explore` → `midscene_tech` explore | `func_agent` → `autoglm_phone_tech` 或 `midscene_tech`（`executor` 择路） |
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
    A3[AnalysisAgent + CASE_GEN_*]
    A4[编辑 / convert-format]
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
    B3[executor → autoglm 或 midscene]
    B4[test_runs]
    B1 --> B2 --> B3 --> B4
  end

  A5 -->|test_cases| B2
  F6 -.->|可选：参考功能树写用例| A2
```

**实现提示**：生成接口校验实例为分析类（`catalog_robot_id` / 目录约定）；执行接口校验实例为执行类且与用例格式、引擎一致。详见 `case_generation.py`、`routers/test_cases.py`、`executor.py`。

## 2. 技术栈总览

| 层级 | 技术 | 语言 |
|------|------|------|
| 前端框架 | Vue 3（Composition API） | JavaScript |
| 前端构建 | Vite 6 | JS / Node |
| 前端路由 | Vue Router 4 | JS |
| 前端状态 | Pinia | JS |
| HTTP 客户端 | Axios | JS |
| 后端框架 | FastAPI | Python 3 |
| ASGI 服务器 | Uvicorn（`standard`） | Python |
| ORM | SQLAlchemy 2.x | Python |
| 校验 / Schema | Pydantic v2 | Python |
| 认证 | JWT（`python-jose`）+ 密码哈希（`bcrypt`） | Python |
| 数据库 | MySQL 8（`DATABASE_URL`） | PyMySQL |
| Agent / LLM | `openai` 官方 SDK（兼容 OpenAI 风格 Base URL） | Python |
| 图像 | Pillow（`PIL`，Agent 侧截图等） | Python |
| 设备 | ADB（Android）、HDC（鸿蒙） | — |
| 视觉自动化 | Midscene.js（`@midscene/android`、`@midscene/harmony`） | TypeScript / Node |
| GUI Grounding | MAI-UI（本地 MLX / Ollama） | Python |

依赖清单：

- AutoGLM Agent（根目录）：`requirements.txt`
- Midscene Agent：`midscene_tech/package.json`
- Web 后端：`web/backend/requirements.txt`
- Web 前端：`web/frontend/package.json`

## 3. 目录结构

```
autoglm-phone-test-agent/          # 仓库根目录
├── ARCHITECTURE.md                # 本文档
├── agent_service/analysis_agent/                # 测试分析：用例生成 + feature_explore/ 功能点分析
├── agent_service/func_agent/                    # 功能测试机器人统一业务域（对外调度入口）
│   ├── orchestrator.py
│   ├── core.py
│   └── backends/
│       ├── autoglm_runner.py
│       ├── autoglm/agent.py
│       └── midscene/runtime.py
├── agent_service/service/                       # agent_service Web 服务（独立进程，端口 8100）
│   ├── app.py                                   #   FastAPI app、lifespan、路由挂载
│   ├── __main__.py                              #   python -m agent_service.service
│   ├── task_manager.py                          #   内存任务注册表（SSE 推流 + 取消）
│   ├── schemas.py / sse.py / config.py          #   模型、SSE 工具、服务配置
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
├── docker-compose.yml             # 本地 MySQL 8（docker compose up -d mysql）
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
        │   ├── main.py            # FastAPI 入口、CORS、挂载路由
        │   ├── database.py        # DATABASE_URL、MySQL engine、ensure_schema
        │   ├── models.py          # SQLAlchemy ORM；MySQL 大字段用 LongText（LONGTEXT）
        │   ├── schemas.py         # Pydantic 出入参
        │   ├── deps.py            # get_current_user（JWT）
        │   ├── auth_utils.py      # 密码、JWT
        │   ├── executor.py        # 测试执行：按 test_agent_backend × 平台路由两技术路线
        │   ├── services/
        │   │   ├── case_generation.py   # Web 适配 → AnalysisAgent；可选转 YAML
        │   │   ├── feature_analysis_bridge.py  # Web 适配 → FeatureExploreAgent → explore
        │   │   ├── case_agent_text.py   # structured → 执行用自然语言（含虚拟键盘提示）
        │   │   ├── case_kb.py           # 用例 KB 扁平检索（RAG 参考）
        │   │   ├── device_platform.py   # 平台/终端解析（实例默认 + 本次覆盖）
        │   │   ├── device_discovery.py  # adb devices / hdc list targets（3s TTL 缓存）
        │   │   └── device_screen.py     # 投屏：ADB / HDC
        │   └── routers/
        │       ├── auth.py
        │       ├── test_cases.py
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
    AA["AnalysisAgent\n用例生成 · 同进程"]
    FE["FeatureExploreAgent\n功能点分析 · 编排"]
    PTA["autoglm_phone_tech\n同进程 · ADB/HDC"]
    MSProc["midscene_tech 子进程"]
    LLMGen["OpenAI 兼容 API\nCASE_GEN_*"]
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
  ASApp -->|"generate_case_draft"| AA --> LLMGen
  ASApp -->|"explore run"| FE --> MSProc
  ASApp -->|"func-agent dispatch"| PTA --> LLM1
  ASApp -->|"func-agent dispatch"| MSProc
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

前端 Axios 使用 `VITE_API_BASE`（可为空）。开发时常为空，请求走同源 `/api`，由 Vite 转发到后端。

agent_service 由 web 后端通过 `app/services/agent_service_client.py`（HTTP 客户端）调用，不再使用 Python `import`。长任务（测试执行、功能探索）先 POST 提交获取 `task_id`，再 GET SSE stream 接收事件，DELETE 取消。

### 4.2 请求链路（登录后）

1. 浏览器 → `POST /api/auth/login`（或 register）→ 返回 JWT。  
2. 前端 `localStorage` 存 token，后续请求 `Authorization: Bearer ...`。  
3. 用例列表 → `GET /api/test-cases`。
3b. **AI 生成草稿** → `POST /api/test-cases/generate`；`case_generation` → HTTP `POST /api/agent/analysis/generate-case-draft` → agent_service `AnalysisAgent`；**不写库**直至 `POST /api/test-cases`。须**测试分析**实例；与功能点分析、用例执行**互斥**（见 §1.4）。  
3c. **功能点分析** → `POST /api/projects/{id}/feature-analysis/runs`；`feature_analysis_bridge` → HTTP submit → agent_service `FeatureExploreAgent` SSE stream → Midscene `explore`；轮询 `GET …/runs/{id}`；结束后 `POST …/confirm` → `project_feature_trees`（成功/取消/失败且有功能点均可）。详见 §4.6。  
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
   - agent_service 内部按 `backend` 路由到 `autoglm_runner`（同进程）或 `midscene.runtime`（子进程）。  
5. Midscene 事件：`kind: meta|step|done` → `step_log`；成功可写 `report_path`。  
6. 取消：`signal_cancel(run_id)` 同时设置本地 `threading.Event` + 通过 `_run_task_ids` 查找 `task_id` 直接 HTTP DELETE 到 agent_service，确保 SSE 流立即中断；前端 `POST …/runs/{id}/cancel`。  
7. 投屏：`GET …/device-screen?device_platform=&device_id=`，与用例页当前选择一致（`device_screen.py`）。

### 4.4 WebSocket 运行监控（大屏）

1. 浏览器打开 `/monitor`（仅 `platform_admin` / `tse`），使用 **同源 WebSocket** `ws(s)://…/api/ws/monitor/robots?token=<JWT>`（开发时走 Vite `/api` 代理，`vite.config.js` 需 `ws: true`）。  
2. 后端 `accept` 后校验 JWT 与角色，随后按固定间隔（约 2s）推送 JSON：`online`、`idle`、`executing`；其中 **executing** 与库表 `test_runs` 中 `status=running` 条数一致，**idle** 等可由 `app/services/robot_monitor.py` 占位模拟，对接 Agent 管理服务后改为拉取/订阅同一指标源。  
3. 断线后前端可指数退避重连，用于展示与运营值守场景。

## 5. 数据存储

- **数据库（MySQL 8）**  
  - 环境变量 **`DATABASE_URL`** 或 **`TCM_DATABASE_URL`**，例如 `mysql+pymysql://user:pass@host:3306/tcm?charset=utf8mb4`。驱动 **PyMySQL**（见 `web/backend/requirements.txt`）。连接池：`TCM_DB_POOL_SIZE`（默认 10）、`TCM_DB_MAX_OVERFLOW`（默认 20）。本地实例：仓库根 **`docker-compose.yml`** → `docker compose up -d mysql`（默认库/用户/密码均为 `tcm`）。  
  - **大字段**：`models.py` 中 `LongText = Text().with_variant(LONGTEXT, "mysql")`，用于 `step_log`、`feature_json` 等。  
  - **启动与健康**：`main.py` 启动时 `create_all` + `ensure_schema()`；`GET /api/health` 执行 `SELECT 1` 并返回 `database: mysql`。  
  - 连接使用 `pool_pre_ping`、`pool_recycle` 与 session `time_zone=+00:00`。  
  - **外部连接（CLI / GUI）**：本地 MySQL 在 Docker 中，映射 **`127.0.0.1:3306`**。须指定 `-h 127.0.0.1`，勿用默认 socket（否则会报 `/tmp/mysql.sock`）。应用账号 `tcm`/`tcm`，库 `tcm`；root 为 `root`/`root`（见 `docker-compose.yml`）。示例：`mysql -h 127.0.0.1 -P 3306 -u tcm -ptcm tcm`；或 `docker compose exec mysql mysql -u tcm -ptcm tcm`。

- **表（逻辑）**  
  - `users`：账号与密码哈希、RBAC `role` 等。  
  - `projects`：项目空间（被测应用、测试目标），多租户按 `owner_id`。  
  - `test_cases`：归属 `project_id`；标题、执行说明、前置条件、`steps_json`（步骤与预期）、优先级、`revision_no`。  
  - `test_case_revisions`：每次保存的快照（版本管理）。  
  - `case_kb_documents`：检索用扁平文本（标题/步骤/说明聚合），供 `/api/knowledge/cases/search`。  
  - `robot_instances`：租用实例化后的数字机器人；`instance_code`（DR-xxxxxx）、`test_agent_backend`、`device_platform`（**默认**平台）、`catalog_robot_id` 等。  
  - `test_runs`：`robot_instance_id`、`device_platform` / `device_id`（**本次**执行实际使用）、`pending` / `running` / `success` / `failed` / `cancelled`、`step_log`、`report_path`（Midscene HTML）、`output_message`、`error_trace`。  
  - `project_reports`：项目维度测试报告摘要（供看板「最新报告」）。  
  - `defects`：缺陷（开放/已解决时间），供看板「未处理缺陷存量」趋势。  
  - `billing_preorders`：机器人商城「立即租用」生成的预订单（`pending_payment` 等），对接支付网关前由计费模块写入。  
  - `project_app_artifacts`：项目内上传的安装包路径；`test_case_sets` / `test_case_set_items`：用例集合；`functional_dispatch_tasks`：功能测试下发任务及 Kafka 投递状态快照。
  - `app_explore_runs`：顶栏「功能清单探索」（全局，与项目无关）。
  - `project_feature_analysis_runs`：项目内功能点分析任务（`traverse_mode`、`max_screens`、`max_depth`、`fair_share_per_root`、`feature_json`、`step_log` 等）。
  - `project_feature_trees`：用户确认后的功能树多版本（`tree_json`、`version_label`、`confirmed_at`）。

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
| 编排 | `agent_service/analysis_agent/feature_explore/agent.py` |
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

**与顶栏「功能清单探索」**：后者无项目归属、表 `app_explore_runs`；项目内入口为项目卡片「功能点分析」。

## 6. 外部依赖与环境变量

配置已按服务拆分，不再使用仓库根目录 `.env`：

| 配置文件 | 服务 | 加载方式 |
|----------|------|----------|
| `web/backend/.env` | Web 后端 | `main.py` → `load_dotenv` |
| `agent_service/.env` | Agent Service | `service/app.py` → `load_dotenv` |
| `.env.example` | 参考文档 | 按服务分区的完整变量说明 |

### Web 后端（`web/backend/.env`）

| 变量（示例） | 用途 |
|----------------|------|
| `DATABASE_URL` / `TCM_DATABASE_URL` | MySQL 8 连接字符串 |
| `TCM_DB_POOL_SIZE` / `TCM_DB_MAX_OVERFLOW` | MySQL 连接池（可选） |
| `JWT_SECRET` / `JWT_EXPIRE_MINUTES` | JWT 签名密钥与过期时间 |
| `LOG_LEVEL` / `LOG_FORMAT` / `LOG_SQL` | 日志配置 |
| `TCM_BUILTIN_ADMIN_*` / `TCM_BOOTSTRAP_ADMIN_*` | 内置平台管理员引导 |
| `AGENT_SERVICE_URL` | agent_service 地址（默认 `http://127.0.0.1:8100`） |
| `ADB_DEVICE_ID` / `HDC_DEVICE_ID` / `HDC_HOME` | 设备发现与投屏 |
| `DEVICE_SCREEN_MAX_WIDTH` | 投屏缩略图最大宽度 |
| `KAFKA_*` | 功能测试下发（可选） |
| `TCM_APP_UPLOAD_DIR` / `TCM_APP_UPLOAD_MAX_MB` | App 安装包上传 |

### Agent Service（`agent_service/.env`）

| 变量（示例） | 用途 |
|----------------|------|
| `AGENT_SERVICE_HOST` / `AGENT_SERVICE_PORT` | 监听地址（默认 `0.0.0.0:8100`） |
| `BIGMODEL_API_KEY` / `ZHIPU_API_KEY` | 智谱 API Key（AutoGLM + 用例生成兜底） |
| `OPENAI_BASE_URL` | 智谱网关等 |
| `PHONE_AGENT_MODEL` / `PHONE_AGENT_MAX_STEPS` | AutoGLM 模型与步数上限 |
| `CASE_GEN_API_KEY` | 用例生成 API Key；未设则回退 `BIGMODEL_API_KEY` |
| `CASE_GEN_BASE_URL` | 用例生成网关（如 `https://api.deepseek.com`） |
| `CASE_GEN_MODEL` / `CASE_GEN_TIMEOUT_SEC` | 用例生成模型与超时 |
| `CASE_GEN_USE_KB` / `CASE_GEN_KB_LIMIT` | 同项目用例 RAG |
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
6. **改测试分析**：`agent_service/analysis_agent/`、`agent_service/service/routers/analysis.py`；环境变量在 `agent_service/.env`（`CASE_GEN_*`）。需重启 agent_service。  
7. **数据库**：MySQL 8；`DATABASE_URL` 必填；无 Alembic，列迁移在 `database.ensure_schema()`。  
8. **排查执行失败**：确认实例 **技术路线（autoglm/midscene）**、用例页 **平台+终端**；`adb devices` / `hdc list targets` 与所选 `device_id` 一致；看 `test_runs.device_platform`、`device_id`、`error_trace`、`step_log`；Midscene 报告见 `report_path`。  
9. **排查 AI 生成失败**：确认 `CASE_GEN_API_KEY`（或回退智谱 Key）与 `CASE_GEN_BASE_URL`/`CASE_GEN_MODEL` 匹配；改 `.env` 后重启 Uvicorn；Swagger `POST /api/test-cases/generate` 可直调；非法 JSON 时服务会自动重试一次修复。  

## 8. 一句话小结

**Vue 3 + FastAPI + MySQL 8** 管理用例与租用机器人实例。**测试分析**实例承担 **用例生成**（`CASE_GEN_*`）与 **功能点分析**（Midscene explore → GIIC 功能树确认保存）两项能力；**测试执行**实例在真机上跑用例，由 **`executor` 在 AutoGLM 与 Midscene 间二选一**。同一项目内可先功能点分析、再生成/落库用例、再 `run`；执行与分析前可选 **Android/鸿蒙** 与 **目标终端**。详见 §1.0、§1.4、§4.6。
