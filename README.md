# autoglm-phone-test-agent

基于 **OpenAI 兼容 API** + **ADB** 的 Android UI 自动化代理，以及配套的 **Web 测试用例管理平台**（Vue 3 + FastAPI）。适用于在手机端按自然语言任务执行自动化测试，并在浏览器中管理账号、项目空间、用例与执行记录。

---

## 文档维护约定

| 变更类型 | 建议同步更新的文档 |
|----------|-------------------|
| 新增/调整业务功能、API、路由、数据模型 | **本 README**（模块说明与启动方式 relevant 部分） |
| 架构细节、目录约定、执行链路深度说明 | [`ARCHITECTURE.md`](./ARCHITECTURE.md) |
| 新增环境变量 | [`.env.example`](./.env.example)、[`web/frontend/.env.example`](./web/frontend/.env.example) |

---

## 系统模块一览

### 1. Agent 核心（`autoglm_phone_agent/`）

- **职责**：观察屏幕 → 模型推理 → 通过 ADB 执行点击、输入等动作，循环直至任务结束。
- **依赖**：根目录 [`requirements.txt`](./requirements.txt)；运行时读取仓库根目录 **`.env`**（API Key、模型、ADB 设备等）。
- **CLI 入口**：仓库根目录 [`main.py`](./main.py)，可在终端直接发起单次任务（与 Web 执行共用同一套 Agent 逻辑）。

### 1b. HarmonyOS Agent（`midscene_agent/`）

- **职责**：基于字节跳动 **[Midscene.js](https://midscenejs.com/)**（`@midscene/harmony`），通过 **HDC** 对 **HarmonyOS 6.x / NEXT** APP 做视觉驱动的自然语言自动化测试。
- **依赖**：Node.js ≥ 18；[`midscene_agent/package.json`](./midscene_agent/package.json)；模型变量 `MIDSCENE_MODEL_*`、设备变量 `HDC_*`（见 [`midscene_agent/.env.example`](./midscene_agent/.env.example) 或根目录 `.env`）。
- **CLI**：`cd midscene_agent && npm install && npm run task -- "自然语言任务"`；示例 `npm run demo`；详见 [`midscene_agent/README.md`](./midscene_agent/README.md)。

### 2. Web 后端（`web/backend/`）

| 模块 | 路径 / 路由前缀 | 功能摘要 |
|------|-----------------|----------|
| **认证与用户** | `/api/auth` | 手机/邮箱注册与登录；JWT（payload 含 `role`）；`/me`、资料 PATCH、改密、`/refresh` 刷新令牌 |
| **项目空间** | `/api/projects` | 项目 CRUD；绑定被测应用与测试目标；多租户按 `owner_id` 隔离；`/projects/{id}/dashboard` 聚合执行次数、报告摘要、活跃机器人、缺陷趋势；`/reports`、`/task-summary` 等 |
| **功能测试下发** | `/api/projects/{id}/app-packages`、`case-sets`、`functional-dispatches` | 上传 APK/AAB；维护用例集；`/functional-dispatches` POST 组装载荷写入 Kafka（未配置 `KAFKA_BOOTSTRAP_SERVERS` 时仅落库 `queued_local`）；`/api/device-pools` 设备池占位目录 |
| **数据聚合服务（进程内）** | `app/services/project_dashboard.py` | 从执行记录、`project_reports`、`defects` 等表组装项目看板 JSON（后续可拆独立数据服务） |
| **测试用例与执行** | `/api/test-cases` | 结构化用例（前置条件、步骤+预期、优先级、`revision_no`）；版本快照表 `test_case_revisions`；`POST /test-cases/import` 导入 CSV/XLSX；知识库文档表 `case_kb_documents`；异步执行 Agent（执行文本由结构化字段拼接） |
| **知识库检索（用例）** | `/api/knowledge/cases/search` | 关键词检索扁平文本（可对接 Agent/RAG）；支持 `project_id` 与租户隔离 |
| **RBAC 管理** | `/api/admin` | 平台管理员：用户列表、角色分配、角色字典 |
| **数据看板** | `/api/dashboard` | 按角色返回全平台或租户范围的统计（含项目数、用例数、执行数） |
| **机器人商城与计费** | `/api/marketplace`、`/api/billing` | 登录用户：`GET /marketplace/robots` 获取四大数字机器人目录（档案、能力、按时长/按次计价）；`POST /billing/preorders` 生成预订单并返回前端支付路径；`GET /billing/preorders/{id}` 供收银台拉取待支付单 |
| **运行监控（WebSocket）** | `/api/ws/monitor/robots` | 查询参数 `token`（JWT）；仅 `platform_admin` / `tse`；约每 2s JSON 推送在线/空闲/执行中（执行中与 `test_runs.running` 对齐，空闲等为 Agent 管理占位，可替换为管控服务数据）；逻辑见 `app/services/robot_monitor.py` |
| **平台能力占位** | `/api/platform` | 设备、计费配置、内部机器人目录、企业租用/用量等（对接后续微服务） |
| **基础设施** | `app/database.py`、`executor.py` | SQLite、启动迁移与默认数据；线程池内执行 `PhoneTestAgent` 并写回 `step_log` |

**RBAC 角色（预定义）**：`platform_admin`（平台管理员）、`tse`（内部测试工程师）、`enterprise`（外部企业用户）。详见 `app/rbac.py`。

**ASGI 入口**：`app.main:app`（Uvicorn）。

### 3. Web 前端（`web/frontend/`）

| 区域 | 说明 |
|------|------|
| **登录 / 注册** | 手机号或邮箱；请求可走 API 网关（`VITE_API_BASE`） |
| **项目空间** | 创建/编辑项目；「项目看板」展示度量；「功能测试任务」向导：上传/选用安装包 → 用例集（自建或 AI 占位草稿）→ 设备池 → 下发至 Kafka 队列 |
| **测试用例** | 列表展示优先级与步骤摘要；新建/编辑含前置条件、多步预期、优先级；版本历史；CSV/Excel 导入；执行与步骤日志轮询 |
| **个人中心** | 昵称、头像 URL、公司及改密 |
| **机器人商城** | `/marketplace`：四大数字机器人（测试分析 / 功能执行 / 专项执行 / 质量评估）卡片；「立即租用」选择按时长或按次数后在计费模块生成预订单，并跳转 `/payment` |
| **数据看板** | 展示统计摘要；部分角色可拉取内部机器人目录与企业用量占位 |
| **运行监控大屏** | `/monitor`：仅 `platform_admin` / `tse`；WebSocket 实时指标；本地 **localhost** 开发时默认 **直连 `127.0.0.1:8000` WS**（不经 Vite，避免与 HMR WebSocket 冲突）；详见 `web/frontend/.env.example`（`VITE_WS_DIRECT` / `VITE_WS_HOST`） |
| **用户与角色** | 仅 `platform_admin`：分配用户 RBAC 角色 |

构建与开发依赖：[`web/frontend/package.json`](./web/frontend/package.json)。

---

## 环境变量

- **模板**：复制仓库根目录 [`.env.example`](./.env.example) 为 `.env`，并按注释填写。Agent CLI、Web 后端 **`executor`**、**`main.py` 启动 FastAPI** 均会加载该文件。
- **前端**：可选复制 [`web/frontend/.env.example`](./web/frontend/.env.example)；开发一般留空，由 Vite 将 `/api` 代理到本地后端。
- **变量说明**：以 `.env.example` 为准（含 `BIGMODEL_API_KEY`、`JWT_SECRET`、`TCM_SQLITE_PATH`、`TCM_BOOTSTRAP_ADMIN_*`、`LOG_LEVEL` 等）。

---

## 本地启动方式

### 前置条件

- Python 3.9+（与现有虚拟环境一致即可）
- Node.js（用于前端；版本随团队规范）
- 运行 Agent / 真机执行时需 **ADB**、设备调试及智谱等 **API Key**（配置在根目录 `.env`）

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

```bash
# 仓库根目录，已安装根目录 requirements.txt
pip install -r requirements.txt
python main.py --help
```

具体参数与设备要求见 `autoglm_phone_agent` 包内说明及根目录 `main.py`。

---

## 默认端口与联调关系

| 服务 | 默认端口 | 说明 |
|------|-----------|------|
| 前端（Vite） | 5173 | 浏览器访问 |
| 后端（Uvicorn） | 8000 | 前端 dev 通过代理访问 `/api/*` |

---

## 相关文档

- [ARCHITECTURE.md](./ARCHITECTURE.md)：架构、目录、请求/执行链路、数据库与排障要点。
- OpenAPI：后端启动后访问 `http://127.0.0.1:8000/docs`（Swagger UI）。
