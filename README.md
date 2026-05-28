# autoglm-phone-test-agent

基于 **Web 测试用例管理平台**（Vue 3 + FastAPI），将 **测试分析机器人 Agent**（`agent_service/analysis_agent`，用例生成）与 **测试执行机器人 Agent**（真机自动化）配合使用。测试执行侧已统一到 **`agent_service/func_agent` 业务域**，内部包含两条技术路线：**AutoGLM-Phone**（智谱 + `autoglm_phone_tech`）与 **Midscene.js**（视觉自动化，`midscene_tech`，支持 **Android / 鸿蒙**）。适用于在手机端按自然语言执行自动化测试，并在浏览器中管理账号、项目空间、用例与执行记录；商城中的其他数字机器人品类可继续扩展独立 Agent 与路由。

---

## 文档维护约定

| 变更类型 | 建议同步更新的文档 |
|----------|-------------------|
| 新增/调整业务功能、API、路由、数据模型 | **本 README**（模块说明与启动方式 relevant 部分） |
| 架构细节、目录约定、执行链路深度说明 | [`ARCHITECTURE.md`](./ARCHITECTURE.md) |
| 新增环境变量 | 根目录 [`.env.example`](./.env.example)（Web/Agent）；前端 [`web/frontend/.env.example`](./web/frontend/.env.example) |
| 功能测试机器人（统一域） | `agent_service/func_agent/`（统一调度） + [`autoglm_phone_tech/README.md`](./autoglm_phone_tech/README.md)、[`midscene_tech/README.md`](./midscene_tech/README.md) |
| MAI-UI 技术路线（GUI Grounding） | [`mai_ui_tech/README.md`](./mai_ui_tech/README.md) |

---

## 端到端工作流：测试分析机器人 × 测试执行机器人

平台将 **「用例写出来」** 与 **「在真机上跑起来」** 拆成两条能力线：**测试分析**与 **测试执行** 各对应一类租用的数字机器人实例；**测试执行**在实例上再选择 **AutoGLM 或 Midscene** 技术路线。在同一**项目空间**下串成完整闭环（概念分层、对照表与架构图见 [`ARCHITECTURE.md`](./ARCHITECTURE.md) §1.0、§1.4、§4）。

| 阶段 | 做什么 | 谁参与 | 典型页面 / API |
|------|--------|--------|------------------|
| 1. 项目准备 | 维护被测应用、测试目标等上下文，便于生成与 KB 检索 | 项目空间 | `/api/projects` |
| 1b. 知识库建设 | 上传规范/策略/页面模型等 → 解析索引 →（规范类）平台审核 → 参与检索 | 项目成员 + **platform_admin** | `/projects/:id/knowledge`；审核 `/knowledge/review` |
| 2. 用例生成 | 一句话描述 → LLM 产出草稿 → 人工核对 → **保存入库** | **测试分析**机器人实例（商城「测试分析」目录；**不连手机**） | 测试用例页「创建用例 → **自动生成**」；`POST /api/test-cases/generate`（**202** 异步 Job + 执行过程日志）、`POST /api/test-cases`（持久化） |
| 2b. 功能点分析 | 选已安装/上传 App → 真机界面遍历 → 产出 GIIC 功能树 → 编辑 → **确认保存多版本** | **测试分析**机器人实例（**须连手机**；与用例生成、功能点分析任务互斥） | 项目空间「功能点分析」；`/api/projects/{id}/feature-analysis`；详见 [`ARCHITECTURE.md`](./ARCHITECTURE.md) §4.6 |
| 3. 执行准备 | 租用并启动 **测试执行** 实例，选择 **AutoGLM 或 Midscene** 技术路线并配置默认平台 | **功能执行**等商城目录（实例即测试执行机器人） | 「我的机器人」；`PATCH /api/robot-instances/...` |
| 4. 真机执行 | 选用例 → 选测试执行实例与（可选）本次 Android/鸿蒙 + 目标终端 → 发起运行 → 看日志 / 投屏 / 报告 | 测试执行实例 + ADB/HDC | 测试用例页「执行测试」；`POST /api/test-cases/{id}/run`、`GET /api/test-cases/runs/{id}` |

**要点**：生成使用 `CASE_GEN_*` 与 `agent_service/analysis_agent`，与真机执行的智谱 / Midscene Key 可分开配置；`generate` **不写库**，保存后写入 `test_cases`，再由 `run` 创建 `test_runs`。

### 服务调用流程（LangChain 1.x）

Web 后端（:8000）经 HTTP 调用 **agent_service**（:8100）；分析/执行逻辑在 `agent_service/langchain_platform/`，门面仍为 `analysis_agent` / `func_agent/orchestrator`。对外 API 与 SSE 事件形态**不变**。

| 业务 | Web 入口 | agent_service | LangChain 实现 |
|------|----------|---------------|----------------|
| 用例生成 | `POST /api/test-cases/generate` → **202** + 轮询 `GET …/generate/{job_id}` | `POST …/generate-case-draft` → **202** + SSE | `CaseGenAgenticGraph`（默认）/ `CaseGenChain` |
| 功能点分析 | `POST …/feature-analysis/runs` + SSE | `POST /api/agent/explore/run` + stream | `ExploreOrchestratorGraph` |
| 测试执行 | `POST /api/test-cases/{id}/run` + SSE | `POST /api/agent/func-agent/dispatch` + stream | `FuncDispatchGraph` → AutoGLM / Midscene |

- **时序图（Mermaid）**：[`ARCHITECTURE.md`](./ARCHITECTURE.md) §1.3.1  
- **逐步说明**：[`agent_service/langchain_platform/README.md`](./agent_service/langchain_platform/README.md)  
- **Agentic RAG 知识库**：项目知识库 UI（`/projects/:id/knowledge`）、平台管理员审核（`/knowledge/review`）、机器人 KB+Skill 绑定；**MySQL 元数据 + Qdrant 向量** + DashScope embedding；索引/检索流程见下文 **「Agentic RAG 知识库」** 与 [`ARCHITECTURE.md`](./ARCHITECTURE.md) §4.8。
- **KB（兼容）**：Web `case_kb` 预检索 → `kb_snippets`；`POST /api/internal/knowledge/query` 为主入口，`/api/internal/knowledge/cases/search` 为 LIKE 降级。

---

## Agentic RAG 知识库（索引 · 检索 · 审核）

### 业务流（用户视角）

```
创建知识集合 → 上传文件 / 结构化录入
       ↓
  后台自动索引（parse → chunk → embed）
       ↓
  ┌─ 测试规范/策略（上传）→ 待审核 → 平台管理员通过 → 写入向量库 → 已发布
  └─ 其他类型（执行经验、页面模型、术语表等）→ 索引成功 → 直接已发布
       ↓
  检索测试 / Agent Tool（query_knowledge）→ 语义命中 active 切片
```

- **谁可以做什么**：项目成员管理集合与文档；**仅 `platform_admin`** 可在「后台管理 → 知识库审核」通过/驳回规范类文档。
- **何时能检索**：文档状态为 **已发布**，且切片 `embedding_status=indexed`（Qdrant 有向量）。待审核文档已解析但未入向量库，**不参与检索**。
- **审核范围**：仅 **`source_type=upload` 且 `doc_type` 为 `standard`（测试规范）或 `strategy`（测试策略）** 会进入待审核；上传时若选成「执行经验」等其它类型，**不会**走审核，索引后直接已发布。
- **机器人绑定**：在「我的机器人」为实例选择知识集合 + Skill；Agent 仅检索绑定集合内的 active 文档。

### 索引参数（环境 / 项目 / 单文档）

| 层级 | 配置位置 | 作用 |
|------|----------|------|
| 环境默认 | `web/backend/.env`：`KB_CHUNK_*`、`KB_SEARCH_MIN_SCORE` | 全站兜底 |
| 项目默认 | 知识库页左侧 **「索引设置」** → `project_knowledge_settings.chunk_policy_json` | 本项目多数文档的切片与检索阈值 |
| 单文档覆盖 | 上传 **「高级索引选项」** 或文档 **「索引设置」** → `knowledge_documents.chunk_policy_json` | 仅影响该文档的切片/向量化（不含最低相似度） |

合并优先级：**环境 → 项目 → 文档**。修改项目或文档级切片参数后，须对已有 **已发布** 文档点 **「重建索引」** 才会重切并重 embed。

**切片能力**（`chunkers.py`）：规范/策略类默认 **按章节标题**（如 `6.3 条件分支`）切片；可向量化文本前附加 **【文档】【章节】** 前缀以提升检索命中率。检索侧用 `KB_SEARCH_MIN_SCORE`（项目页可覆盖）过滤低相似度结果。

### 技术栈

| 组件 | 选型 | 说明 |
|------|------|------|
| 元数据 | MySQL 8 | `knowledge_collections` / `knowledge_documents` / `knowledge_chunks` / `skill_profiles` / `robot_instance_bindings` |
| 向量 | **Qdrant** | `qdrant-client`；集合 `tcm_knowledge_chunks`；Dashboard `http://127.0.0.1:6333/dashboard` |
| Embedding | **DashScope `text-embedding-v3`** | OpenAI 兼容 HTTP（`openai` SDK）；`KB_EMBEDDING_*`；Key 未设时回退 `DASHSCOPE_API_KEY` / `MIDSCENE_MODEL_API_KEY` |
| 文档解析 | python-docx / pymupdf / openpyxl / xlrd | TXT·MD·PDF·DOCX·XLSX·HTML·CSV·JSON；单文件 ≤50MB |
| 文本切片 | `chunkers.py` + `chunk_policy.py` | 可配置长度/重叠；规范类 **按章节标题** 切分；embedding 前可选文档/章节前缀；**无 NLTK** |
| 检索阈值 | `KB_SEARCH_MIN_SCORE` + Qdrant `score_threshold` | 默认 0.6；项目「索引设置」可覆盖；设为 `0` 关闭过滤 |
| 索引编排 | `index/pipeline.py` | `ThreadPoolExecutor` 异步；parse → chunk → embed → Qdrant upsert |
| 检索 | `query/service.py` | query embedding → Qdrant 过滤检索 → MySQL 取 snippet |
| Agent 侧 | LangGraph Tool + Internal API | `POST /api/internal/knowledge/query`（Bearer `WEB_SERVICE_TOKEN`） |
| 兼容 RAG | `case_kb` + LIKE | `/api/internal/knowledge/cases/search` 语义失败时降级 |

> **说明**：`requirements.txt` 中含 `llama-index-*` 包，当前生产路径为自研 `app/knowledge/` 模块（`qdrant_store` + DashScope embedding），非 LlamaIndex QueryEngine 运行时。

### 支持的上传格式

TXT、MD、MARKDOWN、MDX、PDF、HTML、HTM、XLSX、XLS、DOCX、CSV、JSON（单文件 ≤ 50MB）。解析实现见 `app/knowledge/ingestion/parsers.py`。

### 常用 API

| 能力 | 方法 / 路径 |
|------|-------------|
| 集合 CRUD | `GET/POST/PATCH/DELETE /api/knowledge/projects/{id}/collections` |
| 上传文档 | `POST …/documents/upload` |
| 结构化录入 | `POST …/documents/structured` |
| 删除文档（含向量） | `DELETE …/documents/{doc_id}` |
| 重建索引 | `POST /api/knowledge/documents/{doc_id}/reindex` |
| 项目索引设置 | `GET/PATCH/DELETE …/projects/{id}/chunk-policy` |
| 文档索引设置 | `GET/PATCH …/projects/{id}/documents/{doc_id}/chunk-policy`（`?reindex=true` 保存后重建） |
| 检索测试 | `GET …/projects/{id}/search?q=…`（响应含 `min_score`） |
| 审核队列 / 审核 | `GET /api/knowledge/review-queue`、`POST …/documents/{id}/review` |
| Agent 语义检索 | `POST /api/internal/knowledge/query` |
| 机器人 KB 绑定 | `PATCH /api/knowledge/robot-instances/{id}/knowledge-binding` |

深度架构、状态机与排查见 [`ARCHITECTURE.md`](./ARCHITECTURE.md) **§4.8**。

---

## 系统模块一览

### 技术栈总览（仓库级）

| 层次 | 技术 |
|------|------|
| 前端 | Vue 3、Vite 6、Pinia、Vue Router、Axios（JavaScript） |
| Web API | FastAPI、Uvicorn、SQLAlchemy 2、Pydantic v2、PyMySQL |
| Agent | LangChain Core 1.4.x、LangGraph 1.2.x、langchain-openai 1.2.x |
| 关系库 | MySQL 8（Docker Compose） |
| 向量库 | **Qdrant**（Docker Compose；`qdrant-client`） |
| Embedding | **DashScope text-embedding-v3**（OpenAI 兼容；`KB_EMBEDDING_*`） |
| 文档解析 | python-docx、pymupdf、openpyxl、xlrd |
| 设备 | ADB（Android）、HDC（HarmonyOS） |
| 视觉执行 | Midscene.js（Node ≥18） |
| LLM 执行 | AutoGLM-Phone（智谱 OpenAI 兼容） |
| 可选追踪 | LangSmith |

本地基础设施：`docker compose up -d mysql qdrant`。架构细节见 [`ARCHITECTURE.md`](./ARCHITECTURE.md) §2、§4.8。

### 1. 功能测试机器人（`agent_service/func_agent/`）— 统一业务域

- **定位**：测试执行侧统一入口，对外暴露调度接口与 CLI，对内编排 AutoGLM 与 Midscene 两条技术路线。
- **关键入口**：`agent_service/func_agent/orchestrator.py`、`agent_service/func_agent/backends/autoglm/agent.py`、`agent_service/func_agent/backends/midscene/runtime.py`。
- **CLI**：`python -m agent_service.func_agent.cli "任务"`。

### 1a. AutoGLM Agent（`autoglm_phone_tech/`）— 测试执行 · 技术路线一（backend resources）

- **定位**：`agent_service/func_agent` 下 AutoGLM 技术后端的资源包（设备桥接、模型客户端、动作处理）。
- **模块**：`device/device_factory.py`、`adb_bridge.py`、`hdc_bridge.py`、`config/apps_harmonyos.py` 等，详见 [`autoglm_phone_tech/README.md`](./autoglm_phone_tech/README.md)。
- **CLI**：`python -m agent_service.func_agent.cli ...`（仓库已移除 `main.py` 兼容入口）。

### 1b. Midscene Agent（`midscene_tech/`）— 测试执行 · 技术路线二（runtime backend）

- **定位**：**测试执行机器人 Agent** 在 **Midscene（视觉）** 路线下的实现包（与 `autoglm_phone_tech` 二选一，由实例 `test_agent_backend=midscene` 触发）。
- **依赖**：Node.js ≥ 18；[`midscene_tech/package.json`](./midscene_tech/package.json)；模型变量 `MIDSCENE_MODEL_*`（或 DashScope 千问）、设备变量 `ADB_DEVICE_ID` / `HDC_*`。
- **CLI**：`cd midscene_tech && npm install && npm run task -- "自然语言任务"`；`npm run explore -- --app-id <bundleName> --name 显示名` 遍历功能菜单树；详见 [`midscene_tech/README.md`](./midscene_tech/README.md)。

### 1c. 测试执行：技术路线 × 设备平台（`robot_instances`）

租用审批或「我的机器人」详情中，为每个**测试执行**实例配置 **技术路线**（`test_agent_backend`）与 **默认设备平台**（`device_platform`）：

| 技术路线 `test_agent_backend` | 设备平台 `device_platform` | 实际链路 |
|------------------------------|---------------------------|----------|
| `autoglm` | `android` | `autoglm_phone_tech` + ADB（智谱） |
| `autoglm` | `harmonyos` | `autoglm_phone_tech` + HDC（参考 [Open-AutoGLM](https://github.com/zai-org/Open-AutoGLM)） |
| `midscene` | `android` | `midscene_tech` + `@midscene/android` |
| `midscene` | `harmonyos` | `midscene_tech` + `@midscene/harmony`（千问/GLM 等） |

- `device_platform` 为实例**默认**值；用例页「本次执行设备」可在执行前切换 Android / 鸿蒙。
- 路由逻辑：`web/backend/app/executor.py`、`app/services/device_platform.py`。

### 1d. 多设备与执行前终端选择（Web 用例页）

同一机器人实例可连接多台 Android 或鸿蒙设备。在「测试用例」页执行前：

| UI | API / 存储 | 说明 |
|----|------------|------|
| 本次执行设备 | `POST …/run` 的 `device_platform` | 覆盖实例默认平台 |
| 目标终端 | `POST …/run` 的 `device_id` | ADB serial 或 HDC target |
| 刷新 | `GET /api/devices/connected?platform=` | 扫描 `adb devices` / `hdc list targets` |

未选终端时回退到 `agent_service/.env` 的 `ADB_DEVICE_ID` / `HDC_DEVICE_ID`（若已配置）。

### 1e. 测试分析机器人 Agent（`agent_service/analysis_agent/`，HTTP 服务调用）

- **职责**：根据项目上下文与用户一句话，调用大模型生成 **structured** 用例草稿（`title` / `preconditions` / `steps` / `task_text` / `priority`）。所有用例统一为结构化格式，Midscene 执行使用 natural 模式自动转换。
- **包**：[`agent_service/analysis_agent/`](./agent_service/analysis_agent/)（门面）+ [`agent_service/langchain_platform/`](./agent_service/langchain_platform/)（`CaseGenChain` / `ExploreOrchestratorGraph` 实现）。
- **Web 适配**：`case_generation.py`（预检 + KB）+ **`case_generation_jobs.py`**（内存 Job、消费 agent SSE、写 `step_log`）。
- **入口**：测试用例页 **「创建用例」→「自动生成」**（须选择已租用的 **测试分析** 机器人实例）→ 轮询时展示 **执行过程**（含 KB 检索、LLM 请求/响应摘要）→ 预览编辑 → `POST /api/test-cases` 保存。
- **与测试执行配合**：保存后的用例与手动编写的用例相同，在列表中选中后用 **测试执行** 类机器人发起 `POST /api/test-cases/{id}/run`；生成与执行使用**不同**的 `robot_instance_id`。完整步骤见上文 **「端到端工作流」** 与架构文档 §1.0、§1.4。
- **API**（生成阶段不写库）：
  - `POST /api/test-cases/generate` — 202 + `job_id`；请求体 `project_id`、`robot_instance_id`（`catalog_robot_id=test_analysis`）、`prompt`
  - `GET /api/test-cases/generate/{job_id}` — `status`（`running` / `success` / `failed` / `cancelled`）、`progress_message`、`step_log`、成功时 `draft`
  - `DELETE /api/test-cases/generate/{job_id}` — 取消进行中的生成
- **与执行 Agent 分离**：不连手机；真机执行由 **测试执行机器人** 通过 HTTP 提交到 agent_service，在 `executor.py` 中按 **AutoGLM / Midscene** 技术路线路由。

**环境变量（`agent_service/.env`）**

| 变量 | 说明 |
|------|------|
| `CASE_GEN_API_KEY` | 用例生成专用 Key；未设时回退 `BIGMODEL_API_KEY` / `ZHIPU_API_KEY` |
| `CASE_GEN_BASE_URL` | OpenAI 兼容网关；未设时回退 `OPENAI_BASE_URL` |
| `CASE_GEN_MODEL` | 模型名，默认 `glm-4-flash` |
| `CASE_GEN_TIMEOUT_SEC` | 单次生成超时（秒），默认 60 |
| `CASE_GEN_USE_KB` | `true`/`false`，是否检索同项目历史用例，默认 `true` |
| `CASE_GEN_KB_LIMIT` | RAG 参考条数上限（1–5），默认 3 |
| `WEB_INTERNAL_API_URL` / `WEB_SERVICE_TOKEN` | agent 侧 KB Retriever 调 Web internal API（与 `web/backend/.env` 相同 token） |

**本地调试示例（DeepSeek）** — 与 AutoGLM/Midscene 执行 Key 独立，见 [`.env.example`](./.env.example)：

```bash
# agent_service/.env
CASE_GEN_API_KEY=sk-...                    # https://platform.deepseek.com/api_keys
CASE_GEN_BASE_URL=https://api.deepseek.com
CASE_GEN_MODEL=deepseek-v4-pro
CASE_GEN_TIMEOUT_SEC=120
```

修改 `agent_service/.env` 后需**重启 agent_service** 生效。

### 1f. Agentic RAG 知识库（`web/backend/app/knowledge/`）

- **定位**：项目级可检索知识（测试规范、策略、页面模型、用例同步等），为用例生成 / 功能分析 / 测试执行提供 **Agentic RAG** 上下文。
- **存储**：MySQL 存文档与切片正文；Qdrant 存向量；上传文件在 `KB_FILE_STORAGE`（默认 `web/backend/data/knowledge`）。
- **索引**：`index/pipeline.py` — 异步 parse → chunk → DashScope embed → Qdrant upsert。
- **检索**：`query/service.py` — query 向量 + Qdrant 过滤 + MySQL snippet。
- **审核**：上传的 **standard / strategy** 须 `platform_admin` 审核通过后才会 embed 入向量库（详见 ARCHITECTURE §4.8.3）；其它 `doc_type` 不强制审核。
- **索引参数**：`chunk_policy.py` 合并环境/项目/文档三级配置；见上文「索引参数」与 ARCHITECTURE §4.8.9。
- **前端**：`ProjectKnowledgeView.vue`（集合、左侧项目索引设置、上传高级索引选项、文档「索引设置」弹窗、检索测试）、`KnowledgeReviewView.vue`（审核）。

### 1g. MAI-UI 技术路线（`mai_ui_tech/`）

- **定位**：GUI Grounding 技术能力（截图 + 文本 -> 坐标），作为独立技术路线模块维护。
- **入口**：Web 侧能力封装在 `web/backend/app/services/mai_ui_service.py`，页面在 `/mai-ui`。
- **文档**：详见 [`mai_ui_tech/README.md`](./mai_ui_tech/README.md)。

### 2. Web 后端（`web/backend/`）

| 模块 | 路径 / 路由前缀 | 功能摘要 |
|------|-----------------|----------|
| **认证与用户** | `/api/auth` | 手机/邮箱注册与登录；JWT（payload 含 `role`）；`/me`、资料 PATCH、改密、`/refresh` 刷新令牌 |
| **项目空间** | `/api/projects` | 项目 CRUD；绑定被测应用与测试目标；多租户按 `owner_id` 隔离；`/projects/{id}/dashboard` 聚合执行次数、报告摘要、活跃机器人、缺陷趋势；`/reports`、`/task-summary` 等 |
| **功能测试下发** | `/api/projects/{id}/app-packages`、`case-sets`、`functional-dispatches` | 上传 APK/AAB；维护用例集；`/functional-dispatches` POST 组装载荷写入 Kafka（未配置 `KAFKA_BOOTSTRAP_SERVERS` 时仅落库 `queued_local`）；`/api/device-pools` 设备池占位目录 |
| **数据聚合服务（进程内）** | `app/services/project_dashboard.py` | 从执行记录、`project_reports`、`defects` 等表组装项目看板 JSON（后续可拆独立数据服务） |
| **测试用例与执行** | `/api/test-cases` | 结构化用例（`steps_json` + `task_text`）；**测试分析**：`POST /generate`（202 Job）→ 轮询草稿 + `step_log`；**测试执行**：`POST /{id}/run` → `executor` → agent_service SSE；`test_runs` 记录本次平台与终端 |
| **Internal KB（服务间）** | `/api/internal/knowledge/cases/search` | Bearer `WEB_SERVICE_TOKEN`；供 agent `WebCaseKbRetriever`，不面向浏览器 |
| **已连接设备** | `/api/devices/connected` | 按平台枚举本机 ADB/HDC 在线设备（供用例页「目标终端」） |
| **APP 功能清单探索** | `/api/app-explore` | 顶栏全局探索（与项目无关）；Midscene 遍历；`GET /installed-apps`；`POST /runs` 需 `bundle_id`；完成后导出 Excel |
| **项目功能点分析** | `/api/projects/{id}/feature-analysis` | 测试分析实例 + 真机；`POST …/runs`（`traverse_mode`、`max_screens`、`max_depth`、`fair_share_per_root` 等）；实时 `step_log` / 投屏；`POST …/runs/{id}/confirm` 保存确认树（**成功 / 已取消 / 失败且已有功能点**均可）；多版本 `project_feature_trees`（默认版本标签 **`{应用名}-vN`**，同步知识库 `feature_tree` 文档） |
| **知识库检索（用例）** | `/api/knowledge/cases/search` | 语义检索优先，无向量时回退 LIKE |
| **项目知识库** | `/api/knowledge/projects/{id}/collections` 等 | 集合/文档 CRUD、上传（多格式 ≤50MB、可选文档级 `chunk_policy_json`）、项目/文档索引设置、检索测试、删除、重建索引 |
| **Internal Agentic RAG** | `POST /api/internal/knowledge/query` | Bearer `WEB_SERVICE_TOKEN`；LangGraph Tool 主入口 |
| **机器人 KB 绑定** | `PATCH /api/knowledge/robot-instances/{id}/knowledge-binding` | 绑定 knowledge_collections + skill_profile |
| **知识库审核** | `/api/knowledge/review-queue`、`POST …/documents/{id}/review` | 仅 `platform_admin`；通过后触发向量索引 |
| **RBAC 管理** | `/api/admin` | 平台管理员：用户列表、角色分配、角色字典 |
| **数据看板** | `/api/dashboard` | 按角色返回全平台或租户范围的统计（含项目数、用例数、执行数） |
| **机器人商城与计费** | `/api/marketplace`、`/api/billing` | 登录用户：`GET /marketplace/robots` 获取四大数字机器人目录（档案、能力、按时长/按次计价）；`POST /billing/preorders` 生成预订单并返回前端支付路径；`GET /billing/preorders/{id}` 供收银台拉取待支付单 |
| **运行监控（WebSocket）** | `/api/ws/monitor/robots` | 查询参数 `token`（JWT）；仅 `platform_admin` / `tse`；约每 2s JSON 推送在线/空闲/执行中（执行中与 `test_runs.running` 对齐，空闲等为 Agent 管理占位，可替换为管控服务数据）；逻辑见 `app/services/robot_monitor.py` |
| **平台能力占位** | `/api/platform` | 设备、计费配置、内部机器人目录、企业租用/用量等（对接后续微服务） |
| **机器人实例** | `/api/robot-instances` | 已租用实例列表；PATCH 展示名、引擎、`device_platform`（默认平台）；`GET …/device-screen` 支持 `device_platform`、`device_id` 投屏 |
| **基础设施** | `app/database.py`、`executor.py` | MySQL 8（`DATABASE_URL`）、启动迁移；通过 HTTP 调用 agent_service（`agent_service_client.py`）执行 AutoGLM / Midscene 路线，SSE 接收步骤日志与结果 |

**RBAC 角色（预定义）**：`platform_admin`（平台管理员）、`tse`（内部测试工程师）、`enterprise`（外部企业用户）。详见 `app/rbac.py`。

**ASGI 入口**：`app.main:app`（Uvicorn）。

### 3. Web 前端（`web/frontend/`）

| 区域 | 说明 |
|------|------|
| **登录 / 注册** | 手机号或邮箱；请求可走 API 网关（`VITE_API_BASE`） |
| **项目空间** | 创建/编辑项目；「项目看板」展示度量；「功能测试任务」向导：上传/选用安装包 → 用例集（自建或 AI 占位草稿）→ 设备池 → 下发至 Kafka 队列 |
| **测试用例** | 结构化步骤 + 执行说明；**AI 生成**（测试分析实例，异步 Job + **执行过程** 面板）→ 编辑后保存；保存后用 **功能执行** 实例发起运行；执行前选机器人、**本次平台**（Android/鸿蒙）、**目标终端**；步骤日志与报告；多任务并行时工作台 Tab 区分进行中 / 已结束 |
| **我的机器人** | 查看实例编号；配置 **执行引擎** 与 **默认执行设备**（平台）；运行中 **测试执行** 实例点 **执行详情** → `/runs/:runId/live`；**测试分析** 实例功能点分析进行中点 **分析详情** → `/projects/:id/feature-analysis?runId=`（步骤日志 + 投屏）；用例页可临时覆盖 |
| **个人中心** | 昵称、头像 URL、公司及改密 |
| **机器人商城** | `/marketplace`：四大数字机器人（测试分析 / 功能执行 / 专项执行 / 质量评估）卡片；「立即租用」选择按时长或按次数后在计费模块生成预订单，并跳转 `/payment` |
| **数据看板** | 展示统计摘要；部分角色可拉取内部机器人目录与企业用量占位 |
| **运行监控大屏** | `/monitor`：仅 `platform_admin` / `tse`；WebSocket 实时指标；本地 **localhost** 开发时默认 **直连 `127.0.0.1:8000` WS**（不经 Vite，避免与 HMR WebSocket 冲突）；详见 `web/frontend/.env.example`（`VITE_WS_DIRECT` / `VITE_WS_HOST`） |
| **用户与角色** | 仅 `platform_admin`：分配用户 RBAC 角色 |
| **功能清单探索** | `/app-explore` | 选择 APP ID（bundleName）、Midscene 机器人实例；实时步骤日志与功能树预览；下载 Excel |
| **项目功能点分析** | `/projects/:projectId/feature-analysis` | 选测试分析实例与 App；配置遍历策略（默认 **混合**）、最大界面数/深度、Tab 公平分配；分析中功能树 + 投屏；取消或中断后可确认保存已采集树（版本标签默认 **应用名-vN**）；「功能树记录」查看历史版本 |
| **项目知识库** | `/projects/:projectId/knowledge` | 左侧集合 + **项目索引设置**；文档列表（**自定义索引** 标签、索引设置弹窗、重建索引）；上传（**高级索引选项**）；检索测试 |
| **知识库审核** | `/knowledge/review` | 仅 `platform_admin`；审核测试规范/策略上传文档 |

构建与开发依赖：[`web/frontend/package.json`](./web/frontend/package.json)。

---

## 环境变量

环境变量已按服务拆分，不再使用仓库根目录 `.env`：

| 配置文件 | 服务 | 包含内容 |
|----------|------|---------|
| `web/backend/.env` | Web 后端 | 数据库、JWT、日志、管理员、`AGENT_SERVICE_URL`、`WEB_SERVICE_TOKEN` |
| `agent_service/.env` | Agent Service | LLM Key、模型配置、CASE_GEN_*、`WEB_INTERNAL_API_URL`、`WEB_SERVICE_TOKEN`、MIDSCENE_*、设备连接 |

- **参考文档**：[`.env.example`](./.env.example) 按服务分区列出所有变量。
- **前端**：可选复制 [`web/frontend/.env.example`](./web/frontend/.env.example)；开发一般留空，由 Vite 将 `/api` 代理到本地后端。
- **数据库**：Web 后端通过 **`DATABASE_URL`**（或 **`TCM_DATABASE_URL`**）连接 MySQL 8；本地见下方「数据库（MySQL）」小节。

---

## 本地启动方式

### 前置条件

- Python 3.9+、Node.js ≥ 18（前端 + `midscene_tech`）
- **Web 数据库**：Docker Desktop（或本机 MySQL 8）；见下方数据库小节
- **Android 真机**：ADB、`BIGMODEL_API_KEY`（AutoGLM）或 Midscene 模型 Key
- **鸿蒙真机**：HDC（DevEco toolchains）、Midscene 模型 Key；AutoGLM+鸿蒙组合另需智谱 Key
- 环境变量模板仅保留仓库根目录 [`.env.example`](./.env.example)（按分区复制到 `web/backend/.env` 与 `agent_service/.env`）；各服务目录下不再单独维护 `.env.example`。

### 0. 数据库（MySQL 8）

仓库根目录 [`docker-compose.yml`](./docker-compose.yml) 提供本地 MySQL 8（utf8mb4、InnoDB）：

```bash
# 仓库根目录（知识库检索还需 Qdrant，建议一并启动）
docker compose up -d mysql qdrant
```

在 `web/backend/.env` 中配置（与 compose 默认账号一致）：

```bash
DATABASE_URL=mysql+pymysql://tcm:tcm@127.0.0.1:3306/tcm?charset=utf8mb4
```

大文本字段（`step_log`、`feature_json` 等）在 ORM 中映射为 MySQL `LONGTEXT`。

**外部终端 / 客户端连接**（MySQL 跑在 Docker 内，须走 **TCP**，不能省略 `-h`）：

| 项 | 值 |
|----|-----|
| 主机 | `127.0.0.1` |
| 端口 | `3306` |
| 库名 | `tcm` |
| 应用账号 | `tcm` / `tcm` |
| root（仅管理） | `root` / `root` |

```bash
# 本机已安装 mysql 客户端时（推荐应用账号）
mysql -h 127.0.0.1 -P 3306 -u tcm -ptcm tcm

# 或 root
mysql -h 127.0.0.1 -P 3306 -u root -proot tcm

# 未装客户端：进容器执行
docker compose exec mysql mysql -u tcm -ptcm tcm
```

若执行 `mysql -u root -proot` 报 `Can't connect through socket '/tmp/mysql.sock'`，是因为客户端在找**本机安装的 MySQL**，而实际服务在 Docker 映射的 `127.0.0.1:3306`。Navicat、DBeaver、TablePlus 等 GUI 同样填 **Host=127.0.0.1、Port=3306**。

查看容器状态：`docker compose ps`；数据卷持久化见 `docker-compose.yml` 中 `tcm_mysql_data`。

### 0b. 向量库（Qdrant）

知识库向量索引由 Qdrant 承载（与 MySQL 元数据分离）。仓库根目录 `docker-compose.yml`：

```bash
# 仓库根目录（可与 mysql 一并启动）
docker compose up -d qdrant
# 或：docker compose up -d mysql qdrant
```

在 `web/backend/.env` 中配置（见 [`.env.example`](./.env.example)）：

```bash
QDRANT_URL=http://127.0.0.1:6333
QDRANT_COLLECTION=tcm_knowledge_chunks
```

**Web 管理界面（Dashboard）**

| 项 | 地址 |
|----|------|
| **Dashboard（推荐）** | [http://127.0.0.1:6333/dashboard](http://127.0.0.1:6333/dashboard) |
| REST API 根路径 | `http://127.0.0.1:6333/`（返回版本 JSON，用于健康检查） |
| gRPC | `127.0.0.1:6334`（本应用经 HTTP 访问，一般无需浏览器打开） |

浏览器打开 Dashboard 后可查看集合 `tcm_knowledge_chunks`（默认名，与 `QDRANT_COLLECTION` 一致）、向量点 payload（`chunk_id`、`doc_type`、`project_id` 等）。文档经 Web 后端 ingest 后写入该集合；**仅 `status=active` 且已 indexed 的切片**参与检索（规范类须先通过知识库审核）。

**索引与检索配置**（`web/backend/.env`）：

```bash
KB_EMBEDDING_API_KEY=sk-...          # 或 DASHSCOPE_API_KEY
KB_EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
KB_EMBEDDING_MODEL=text-embedding-v3
KB_FILE_STORAGE=web/backend/data/knowledge
KB_SEARCH_MIN_SCORE=0.6
KB_CHUNK_MAX_CHARS=800
KB_CHUNK_OVERLAP=100
KB_CHUNK_HEADING_AWARE=1
RAG_DEFAULT_MODE=agentic
```

项目页「索引设置」与单文档设置会覆盖上述切片/阈值默认值；详见 §「索引参数（环境 / 项目 / 单文档）」。

完整流程与状态机见 [`ARCHITECTURE.md`](./ARCHITECTURE.md) §4.8。

数据卷：`tcm_qdrant_data`（见 `docker-compose.yml`）。

### 1. Web 后端（FastAPI）

```bash
cd web/backend
python -m venv .venv          # 若尚未创建虚拟环境
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 在 web/backend/.env 已配置的前提下：
PYTHONPATH=. uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level info
```

- `app/logging_config.py` 将 Python 侧「应用类」日志默认设为 **INFO**（可用环境变量 **`LOG_LEVEL`** 覆盖）；启动参数 **`--log-level info`** 用于 Uvicorn 自身的访问/错误输出。
- 未激活 venv 时也可：`web/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level info`（需在 `web/backend` 下执行或配置 `PYTHONPATH`）。
- 健康检查：`GET http://127.0.0.1:8000/api/health` → `{"status":"ok","database":"mysql"}`（含数据库连通探测）

### 1b. Agent Service（FastAPI · 独立进程）

```bash
cd agent_service
python -m venv .venv          # 若尚未创建虚拟环境
source .venv/bin/activate
pip install -r requirements.txt

# 在 agent_service/.env 已配置的前提下：
python -m agent_service.service
# 或：uvicorn agent_service.service.app:app --host 0.0.0.0 --port 8100
```

- 健康检查：`GET http://127.0.0.1:8100/api/agent/health` → `{"status":"ok"}`
- Swagger 文档：`http://127.0.0.1:8100/docs`
- 须在 web backend 启动前运行，或后端会显示 agent_service 不可达提示

### 2. Web 前端（Vite）

```bash
cd web/frontend
npm install
npm run dev
```

- 默认开发地址：**http://localhost:5173**
- `vite.config.js` 将 **`/api` 代理到 `http://127.0.0.1:8000`**，与后端端口一致即可联调。

### 3. Agent CLI（可选）

**Func Agent CLI（AutoGLM 路线，Android / 鸿蒙）**

```bash
pip install -r requirements.txt

# Android
adb devices
python -m agent_service.func_agent.cli "打开美团搜索附近的火锅店"

# 鸿蒙（同 Open-AutoGLM --device-type hdc）
hdc list targets
python -m agent_service.func_agent.cli --device-type hdc "打开设置并进入关于本机"
```

**Midscene（Android / 鸿蒙，默认鸿蒙）**

```bash
cd midscene_tech && npm install
npm run task -- --check-hdc          # 鸿蒙：检查 HDC
MIDSCENE_DEVICE_PLATFORM=android npm run task -- "打开设置"   # Android
npm run task -- "打开设置并进入关于本机"                        # 鸿蒙（默认）
```

---

## 默认端口与联调关系

| 服务 | 默认端口 | 说明 |
|------|-----------|------|
| 前端（Vite） | 5173 | 浏览器访问 |
| 后端（Uvicorn） | 8000 | 前端 dev 通过代理访问 `/api/*` |
| Agent Service | 8100 | agent_service Web 服务；web 后端通过 HTTP 调用 |
| MySQL | 3306 | `docker compose up -d mysql` |
| Qdrant HTTP / Dashboard | 6333 | API：`http://127.0.0.1:6333`；界面：`http://127.0.0.1:6333/dashboard` |
| Qdrant gRPC | 6334 | 可选；应用默认用 HTTP |

---

## 相关文档

- [ARCHITECTURE.md](./ARCHITECTURE.md)：架构、目录、请求/执行链路、数据库与排障要点；**知识库索引/检索**见 §4.8，**技术栈**见 §2。
- [autoglm_phone_tech/README.md](./autoglm_phone_tech/README.md)：AutoGLM 双平台设备层与 CLI。
- [midscene_tech/README.md](./midscene_tech/README.md)：Midscene 视觉自动化。
- [Open-AutoGLM](https://github.com/zai-org/Open-AutoGLM)：上游 Phone Agent 参考实现。
- OpenAPI：后端启动后访问 `http://127.0.0.1:8000/docs`（Swagger UI）。
