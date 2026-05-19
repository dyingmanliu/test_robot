# autoglm-phone-test-agent

基于 **AutoGLM-Phone**（智谱 + ADB）与 **Midscene.js**（视觉自动化，支持 **Android / 鸿蒙**）的移动端 UI 自动化，以及配套的 **Web 测试用例管理平台**（Vue 3 + FastAPI）。适用于在手机端按自然语言或 YAML 脚本执行自动化测试，并在浏览器中管理账号、项目空间、用例与执行记录。

---

## 文档维护约定

| 变更类型 | 建议同步更新的文档 |
|----------|-------------------|
| 新增/调整业务功能、API、路由、数据模型 | **本 README**（模块说明与启动方式 relevant 部分） |
| 架构细节、目录约定、执行链路深度说明 | [`ARCHITECTURE.md`](./ARCHITECTURE.md) |
| 新增环境变量 | [`.env.example`](./.env.example)、[`web/frontend/.env.example`](./web/frontend/.env.example) |
| Agent 设备层 / 双平台 | [`autoglm_phone_agent/README.md`](./autoglm_phone_agent/README.md)、[`midscene_agent/README.md`](./midscene_agent/README.md) |

---

## 系统模块一览

### 1. AutoGLM Agent（`autoglm_phone_agent/`）

- **职责**：观察屏幕 → 模型推理 → 执行 UI 动作（**Android/ADB** 或 **鸿蒙/HDC**），对齐 [Open-AutoGLM](https://github.com/zai-org/Open-AutoGLM) 的 `device_factory` 设计。
- **模块**：`device/device_factory.py`、`adb_bridge.py`、`hdc_bridge.py`、`config/apps_harmonyos.py` 等，详见 [`autoglm_phone_agent/README.md`](./autoglm_phone_agent/README.md)。
- **CLI**：`python main.py "任务"`（Android）；`python main.py --device-type hdc "任务"`（鸿蒙）。

### 1b. Midscene Agent（`midscene_agent/`）

- **职责**：基于字节跳动 **[Midscene.js](https://midscenejs.com/)**，在 **Android**（`@midscene/android` + ADB）与 **鸿蒙**（`@midscene/harmony` + HDC）上做视觉驱动的自然语言 / YAML 自动化。
- **依赖**：Node.js ≥ 18；[`midscene_agent/package.json`](./midscene_agent/package.json)；模型变量 `MIDSCENE_MODEL_*`（或 DashScope 千问）、设备变量 `ADB_DEVICE_ID` / `HDC_*`。
- **CLI**：`cd midscene_agent && npm install && npm run task -- "自然语言任务"`；`npm run explore -- --app-id <bundleName> --name 显示名` 遍历功能菜单树；详见 [`midscene_agent/README.md`](./midscene_agent/README.md)。

### 1c. 执行引擎 × 设备平台（Web 机器人实例）

租用审批或「我的机器人」详情中，为每个实例配置两个维度（存于 `robot_instances` 表）：

| 执行引擎 `test_agent_backend` | 设备平台 `device_platform` | 实际链路 |
|------------------------------|---------------------------|----------|
| `autoglm` | `android` | `autoglm_phone_agent` + ADB（智谱） |
| `autoglm` | `harmonyos` | `autoglm_phone_agent` + HDC（参考 [Open-AutoGLM](https://github.com/zai-org/Open-AutoGLM)） |
| `midscene` | `android` | `midscene_agent` + `@midscene/android` |
| `midscene` | `harmonyos` | `midscene_agent` + `@midscene/harmony`（千问/GLM 等） |

- **YAML 用例**仅支持 **Midscene 引擎**（平台可选 Android 或鸿蒙）。
- `device_platform` 为实例**默认**值；用例页「本次执行设备」可在执行前切换 Android / 鸿蒙。
- 路由逻辑：`web/backend/app/executor.py`、`app/services/device_platform.py`。

### 1d. 多设备与执行前终端选择（Web 用例页）

同一机器人实例可连接多台 Android 或鸿蒙设备。在「测试用例」页执行前：

| UI | API / 存储 | 说明 |
|----|------------|------|
| 本次执行设备 | `POST …/run` 的 `device_platform` | 覆盖实例默认平台 |
| 目标终端 | `POST …/run` 的 `device_id` | ADB serial 或 HDC target |
| 刷新 | `GET /api/devices/connected?platform=` | 扫描 `adb devices` / `hdc list targets` |

未选终端时回退到 `.env` 的 `ADB_DEVICE_ID` / `HDC_DEVICE_ID`（若已配置）。

### 1e. 用例编写 Agent（`analysis_agent/`，Web 同进程调用）

- **职责**：根据项目上下文与用户一句话，调用大模型生成 **structured** 用例草稿（`title` / `preconditions` / `steps` / `task_text` / `priority`）。LLM 始终产出结构化字段；若前端选择 YAML，由 `case_format_convert.py` 转为 Midscene `tasks:` 脚本。
- **包**：[`analysis_agent/`](./analysis_agent/)（对齐 [`autoglm_phone_agent/`](./autoglm_phone_agent/) 模式：`AnalysisAgent` + `model/client` + `config`）。
- **Web 适配**：`web/backend/app/services/case_generation.py` 组装 ORM / KB，调用 `AnalysisAgent.generate_case_draft()`；可选 `case_format=yaml` 时在生成后做格式转换。
- **格式互转**：`web/backend/app/services/case_format_convert.py` — structured ↔ Midscene YAML（规则转换，编辑弹窗切换格式时调用）。
- **入口**：测试用例页 **「创建用例」→「自动生成」**（须选择已租用的 **测试分析** 机器人实例；可选生成格式）→ 预览编辑（可再切换格式）→ `POST /api/test-cases` 保存。
- **API**（均不写库）：
  - `POST /api/test-cases/generate` — 请求体 `project_id`、`robot_instance_id`（`catalog_robot_id=test_analysis`）、`prompt`、可选 `case_format`（`structured` | `yaml`，默认 `structured`）
  - `POST /api/test-cases/convert-format` — 编辑时 structured ↔ yaml 互转
- **与执行 Agent 分离**：不连手机；执行仍由 AutoGLM / Midscene 在 `executor.py` 路由。YAML 用例须 **Midscene** 引擎执行。

**环境变量（仓库根 `.env`）**

| 变量 | 说明 |
|------|------|
| `CASE_GEN_API_KEY` | 用例生成专用 Key；未设时回退 `BIGMODEL_API_KEY` / `ZHIPU_API_KEY` |
| `CASE_GEN_BASE_URL` | OpenAI 兼容网关；未设时回退 `OPENAI_BASE_URL` |
| `CASE_GEN_MODEL` | 模型名，默认 `glm-4-flash` |
| `CASE_GEN_TIMEOUT_SEC` | 单次生成超时（秒），默认 60 |
| `CASE_GEN_USE_KB` | `true`/`false`，是否检索同项目历史用例，默认 `true` |
| `CASE_GEN_KB_LIMIT` | RAG 参考条数上限（1–5），默认 3 |

**本地调试示例（DeepSeek）** — 与 AutoGLM/Midscene 执行 Key 独立，见 [`.env.example`](./.env.example)：

```bash
CASE_GEN_API_KEY=sk-...                    # https://platform.deepseek.com/api_keys
CASE_GEN_BASE_URL=https://api.deepseek.com
CASE_GEN_MODEL=deepseek-v4-pro
CASE_GEN_TIMEOUT_SEC=120
```

修改 `.env` 后需**重启 Uvicorn** 生效。

### 2. Web 后端（`web/backend/`）

| 模块 | 路径 / 路由前缀 | 功能摘要 |
|------|-----------------|----------|
| **认证与用户** | `/api/auth` | 手机/邮箱注册与登录；JWT（payload 含 `role`）；`/me`、资料 PATCH、改密、`/refresh` 刷新令牌 |
| **项目空间** | `/api/projects` | 项目 CRUD；绑定被测应用与测试目标；多租户按 `owner_id` 隔离；`/projects/{id}/dashboard` 聚合执行次数、报告摘要、活跃机器人、缺陷趋势；`/reports`、`/task-summary` 等 |
| **功能测试下发** | `/api/projects/{id}/app-packages`、`case-sets`、`functional-dispatches` | 上传 APK/AAB；维护用例集；`/functional-dispatches` POST 组装载荷写入 Kafka（未配置 `KAFKA_BOOTSTRAP_SERVERS` 时仅落库 `queued_local`）；`/api/device-pools` 设备池占位目录 |
| **数据聚合服务（进程内）** | `app/services/project_dashboard.py` | 从执行记录、`project_reports`、`defects` 等表组装项目看板 JSON（后续可拆独立数据服务） |
| **测试用例与执行** | `/api/test-cases` | 结构化用例与 Midscene YAML；`POST /generate`（可选 `case_format`）AI 生成草稿；`POST /convert-format` 格式互转；`POST /{id}/run` 支持 `robot_instance_id`、`device_platform`、`device_id`；异步 Agent；`test_runs` 记录本次平台与终端 |
| **已连接设备** | `/api/devices/connected` | 按平台枚举本机 ADB/HDC 在线设备（供用例页「目标终端」） |
| **APP 功能清单探索** | `/api/app-explore` | Midscene + HDC DFS 遍历导航菜单；`GET /installed-apps`（`hdc shell bm dump -a`）；`POST /runs` 需 `bundle_id`；完成后导出 Excel |
| **知识库检索（用例）** | `/api/knowledge/cases/search` | 关键词检索扁平文本（可对接 Agent/RAG）；支持 `project_id` 与租户隔离 |
| **RBAC 管理** | `/api/admin` | 平台管理员：用户列表、角色分配、角色字典 |
| **数据看板** | `/api/dashboard` | 按角色返回全平台或租户范围的统计（含项目数、用例数、执行数） |
| **机器人商城与计费** | `/api/marketplace`、`/api/billing` | 登录用户：`GET /marketplace/robots` 获取四大数字机器人目录（档案、能力、按时长/按次计价）；`POST /billing/preorders` 生成预订单并返回前端支付路径；`GET /billing/preorders/{id}` 供收银台拉取待支付单 |
| **运行监控（WebSocket）** | `/api/ws/monitor/robots` | 查询参数 `token`（JWT）；仅 `platform_admin` / `tse`；约每 2s JSON 推送在线/空闲/执行中（执行中与 `test_runs.running` 对齐，空闲等为 Agent 管理占位，可替换为管控服务数据）；逻辑见 `app/services/robot_monitor.py` |
| **平台能力占位** | `/api/platform` | 设备、计费配置、内部机器人目录、企业租用/用量等（对接后续微服务） |
| **机器人实例** | `/api/robot-instances` | 已租用实例列表；PATCH 展示名、引擎、`device_platform`（默认平台）；`GET …/device-screen` 支持 `device_platform`、`device_id` 投屏 |
| **基础设施** | `app/database.py`、`executor.py` | SQLite、启动迁移；AutoGLM 同进程（ADB/HDC），Midscene 子进程；写回 `step_log` / Midscene HTML 报告 |

**RBAC 角色（预定义）**：`platform_admin`（平台管理员）、`tse`（内部测试工程师）、`enterprise`（外部企业用户）。详见 `app/rbac.py`。

**ASGI 入口**：`app.main:app`（Uvicorn）。

### 3. Web 前端（`web/frontend/`）

| 区域 | 说明 |
|------|------|
| **登录 / 注册** | 手机号或邮箱；请求可走 API 网关（`VITE_API_BASE`） |
| **项目空间** | 创建/编辑项目；「项目看板」展示度量；「功能测试任务」向导：上传/选用安装包 → 用例集（自建或 AI 占位草稿）→ 设备池 → 下发至 Kafka 队列 |
| **测试用例** | 结构化或 **Midscene YAML**；**AI 生成**可选输出格式（结构化 / YAML）；编辑弹窗可 **structured ↔ YAML 互转**；执行前选机器人、**本次平台**（Android/鸿蒙）、**目标终端**（多机时指定 serial/target）；YAML 须 Midscene 引擎；步骤日志与报告 |
| **我的机器人** | 查看实例编号；配置 **执行引擎** 与 **默认执行设备**（平台）；运行中实例可点 **执行详情** 进入 `/runs/:runId/live` 查看实时进度（步骤日志 + 设备画面）；用例页可临时覆盖 |
| **个人中心** | 昵称、头像 URL、公司及改密 |
| **机器人商城** | `/marketplace`：四大数字机器人（测试分析 / 功能执行 / 专项执行 / 质量评估）卡片；「立即租用」选择按时长或按次数后在计费模块生成预订单，并跳转 `/payment` |
| **数据看板** | 展示统计摘要；部分角色可拉取内部机器人目录与企业用量占位 |
| **运行监控大屏** | `/monitor`：仅 `platform_admin` / `tse`；WebSocket 实时指标；本地 **localhost** 开发时默认 **直连 `127.0.0.1:8000` WS**（不经 Vite，避免与 HMR WebSocket 冲突）；详见 `web/frontend/.env.example`（`VITE_WS_DIRECT` / `VITE_WS_HOST`） |
| **用户与角色** | 仅 `platform_admin`：分配用户 RBAC 角色 |
| **功能清单探索** | `/app-explore` | 选择 APP ID（bundleName）、Midscene 机器人实例；实时步骤日志与功能树预览；下载 Excel |

构建与开发依赖：[`web/frontend/package.json`](./web/frontend/package.json)。

---

## 环境变量

- **模板**：复制仓库根目录 [`.env.example`](./.env.example) 为 `.env`，并按注释填写。Agent CLI、Web 后端 **`executor`**、**`main.py` 启动 FastAPI** 均会加载该文件。
- **前端**：可选复制 [`web/frontend/.env.example`](./web/frontend/.env.example)；开发一般留空，由 Vite 将 `/api` 代理到本地后端。
- **变量说明**：以 `.env.example` 为准。模型侧常用 `BIGMODEL_API_KEY`（智谱 / AutoGLM）、`MIDSCENE_MODEL_*` / `DASHSCOPE_API_KEY`（千问）、`CASE_GEN_*`（用例 **AI 生成**，可与执行模型分离，如 DeepSeek `deepseek-v4-pro`）；设备侧 `ADB_DEVICE_ID`、`HDC_DEVICE_ID` 为可选兜底，**多机时建议在测试用例页选择目标终端**。

---

## 本地启动方式

### 前置条件

- Python 3.9+、Node.js ≥ 18（前端 + `midscene_agent`）
- **Android 真机**：ADB、`BIGMODEL_API_KEY`（AutoGLM）或 Midscene 模型 Key
- **鸿蒙真机**：HDC（DevEco toolchains）、Midscene 模型 Key；AutoGLM+鸿蒙组合另需智谱 Key
- 根目录 `.env` 配置见 [`.env.example`](./.env.example)；使用 **AI 生成用例** 时需配置 `CASE_GEN_API_KEY`（或回退智谱 Key）

### 1. Web 后端（FastAPI）

```bash
cd web/backend
python -m venv .venv          # 若尚未创建虚拟环境
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 在仓库根目录已存在 .env 的前提下：
uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level info
```

- `app/logging_config.py` 将 Python 侧「应用类」日志默认设为 **INFO**（可用环境变量 **`LOG_LEVEL`** 覆盖）；启动参数 **`--log-level info`** 用于 Uvicorn 自身的访问/错误输出。
- 未激活 venv 时也可：`web/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level info`（需在 `web/backend` 下执行或配置 `PYTHONPATH`）。
- **长时间跑任务**时不建议使用 `uvicorn --reload`，以免代码保存重启进程打断后台执行。
- 健康检查：`GET http://127.0.0.1:8000/api/health`

### 2. Web 前端（Vite）

```bash
cd web/frontend
npm install
npm run dev
```

- 默认开发地址：**http://localhost:5173**
- `vite.config.js` 将 **`/api` 代理到 `http://127.0.0.1:8000`**，与后端端口一致即可联调。

### 3. Agent CLI（可选）

**AutoGLM（Android / 鸿蒙）**

```bash
pip install -r requirements.txt

# Android
adb devices
python main.py "打开美团搜索附近的火锅店"

# 鸿蒙（同 Open-AutoGLM --device-type hdc）
hdc list targets
python main.py --device-type hdc "打开设置并进入关于本机"
```

**Midscene（Android / 鸿蒙，默认鸿蒙）**

```bash
cd midscene_agent && npm install
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

---

## 相关文档

- [ARCHITECTURE.md](./ARCHITECTURE.md)：架构、目录、请求/执行链路、数据库与排障要点。
- [autoglm_phone_agent/README.md](./autoglm_phone_agent/README.md)：AutoGLM 双平台设备层与 CLI。
- [midscene_agent/README.md](./midscene_agent/README.md)：Midscene 视觉自动化。
- [Open-AutoGLM](https://github.com/zai-org/Open-AutoGLM)：上游 Phone Agent 参考实现。
- OpenAPI：后端启动后访问 `http://127.0.0.1:8000/docs`（Swagger UI）。
