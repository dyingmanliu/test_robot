# langchain_platform

LangChain **1.x** / LangGraph 统一实现层：`langchain-core` 1.4.x、`langchain-openai` 1.2.x、`langgraph` 1.2.x。

Web 后端（:8000）经 HTTP 调用 agent_service（:8100）；本包不直接面向浏览器。架构总览见仓库根目录 [`ARCHITECTURE.md`](../../ARCHITECTURE.md) §1.3.1。

## 三条业务链路

| 链路 | Web 入口 | agent_service HTTP | 本包入口 |
|------|----------|-------------------|----------|
| 用例生成 | `POST /api/test-cases/generate` | `POST /api/agent/analysis/generate-case-draft` | `CaseGenAgenticGraph`（默认）/ `CaseGenChain`（passive） |
| 功能点分析 | `POST /api/projects/{id}/feature-analysis/runs` | `POST /api/agent/explore/run` + SSE | `ExploreOrchestratorGraph`（含 `prefetch_kb`） |
| 测试执行 | `POST /api/test-cases/{id}/run` | `POST /api/agent/func-agent/dispatch` + SSE | `FuncDispatchGraph`（含 prefetch + AutoGLM Recovery RAG） |

**Agentic RAG Tools**（`tools/knowledge_query.py`）经 HTTP 调 Web `POST /api/internal/knowledge/query`；scope（`robot_instance_id` / `project_id`）由 graph state 注入，LLM 不可改 collection。

---

## 1. 用例生成

```
Vue CasesView
  → POST /api/test-cases/generate                    [web :8000]
  → case_generation.generate_case_draft
       ├─ case_kb.search_cases_kb（MySQL LIKE）      → kb_snippets[]
       └─ agent_service_client.generate_case_draft
            → POST /api/agent/analysis/generate-case-draft   [agent :8100]
            → AnalysisAgent.generate_case_draft
            → CaseGenChain.generate
                 ├─（可选）WebCaseKbRetriever
                 │    → GET /api/internal/knowledge/cases/search
                 │         Authorization: Bearer WEB_SERVICE_TOKEN
                 ├─ ChatOpenAI（CASE_GEN_*）
                 ├─ parser.extract_json_object / draft_from_parsed
                 └─ JSON 解析失败时重试一轮
  ← TestCaseGenerateOut（不写库，用户确认后 POST /api/test-cases）
```

**KB 双路径（可并存）**

| 路径 | 谁检索 | 何时生效 |
|------|--------|----------|
| A | Web `case_generation._fetch_kb_examples` | `CASE_GEN_USE_KB=true`，始终可传 `kb_snippets` 给 agent |
| B | agent `WebCaseKbRetriever` | 请求里 `kb_snippets` 为空且配置了 `WEB_SERVICE_TOKEN` |

合并 `similar_case_ids`：agent 返回的优先，否则用 Web 检索的 case id 列表。

**关键文件**

- `chains/case_generation.py` — LCEL 链
- `retrievers/web_case_kb.py` — HTTP Retriever
- `models.py` — `get_chat_model("case_gen")`
- `analysis_agent/agent.py` — 薄门面

---

## 2. 功能点分析

```
Vue ProjectFeatureAnalysisView
  → POST /api/projects/{id}/feature-analysis/runs     [web]
  → feature_analysis_bridge.execute_feature_analysis_run（后台线程）
       ├─ submit_explore_run → POST /api/agent/explore/run
       └─ stream_explore_events → GET …/explore/run/{id}/stream（SSE）
            → FeatureExploreAgent.run
            → run_explore_graph（LangGraph）
                 validate_dispatch
                 → run_explore（execute_explore_run）
                 → sync_tree（ensure_giic_tree）
            → explore_core → run_midscene_explore_dispatch
            → midscene_tech explore 子进程（JSONL stdout）
       ← 增量写 run.feature_json、step_log
  → GET /runs/{id} 轮询
  → POST /runs/{id}/confirm → project_feature_trees
```

**LangGraph 不负责** Midscene 内视觉 `aiAct` 重规划循环，只负责编排、取消回调、树归一化。

**关键文件**

- `graphs/explore_run.py` — 编排图
- `explore_core.py` — 事件聚合 + 调 Midscene
- `tools/midscene_dispatch.py` — 子进程封装
- `analysis_agent/feature_explore/agent.py` — 门面

---

## 3. 测试执行

```
Vue CasesView
  → POST /api/test-cases/{id}/run                       [web]
  → executor.execute_test_run（线程）
       ├─ case_agent_text.build_agent_task_text / build_midscene_tech_steps
       ├─ submit_func_agent_dispatch
       │    → POST /api/agent/func-agent/dispatch（202 + task_id）
       └─ stream_func_agent_events
            → GET …/func-agent/dispatch/{id}/stream（SSE）
            → run_func_agent_dispatch
            → run_func_dispatch_graph（LangGraph）
                 ├─ backend=autoglm → AutoglmExecGraph
                 │    PhoneTestAgent._execute_step 循环
                 │    SSE event: step
                 └─ backend=midscene → MidsceneExecGraph
                      run_midscene_task 子进程
                      SSE event: line / usage
       ← 写 test_runs.step_log、status、report
  → GET /api/test-cases/runs/{id} 轮询
  → DELETE …/cancel → signal_cancel → DELETE agent task
```

**关键文件**

- `graphs/func_dispatch.py` — 按 `backend` 路由
- `graphs/autoglm_exec.py` — AutoGLM 步进图
- `graphs/midscene_exec.py` — Midscene 薄图
- `tools/device_autoglm.py` — 设备 / Agent 构建
- `func_agent/orchestrator.py` — 门面

---

## 配置

### agent_service/.env

```env
# 用例生成 LLM
CASE_GEN_API_KEY=...
CASE_GEN_BASE_URL=...
CASE_GEN_MODEL=...
CASE_GEN_USE_KB=true
CASE_GEN_KB_LIMIT=3

# KB Retriever → Web（与 web/backend/.env 相同 token）
WEB_INTERNAL_API_URL=http://127.0.0.1:8000
WEB_SERVICE_TOKEN=your-shared-secret

# 执行（AutoGLM / Midscene）
BIGMODEL_API_KEY=...
MIDSCENE_MODEL_*=...

# LangSmith（可选；有 LANGSMITH_API_KEY 时默认开启）
LANGSMITH_API_KEY=...
LANGCHAIN_PROJECT=test-robots
```

### web/backend/.env

```env
AGENT_SERVICE_URL=http://127.0.0.1:8100
WEB_SERVICE_TOKEN=your-shared-secret   # 与 agent_service 一致
DATABASE_URL=mysql+...
```

### Internal API（仅服务间）

| 方法 | 路径 | 鉴权 |
|------|------|------|
| GET | `/api/internal/knowledge/cases/search` | `Authorization: Bearer {WEB_SERVICE_TOKEN}` |

实现：`web/backend/app/routers/internal_knowledge.py`。

---

## Skill 扩展

1. 在 `tools/` 实现 `BaseTool`
2. 在 `tools/registry.py` 的 `SKILLS_BY_CATALOG` 登记
3. 在对应 Chain/Graph 节点挂载

无需修改 FastAPI router。

---

## 安装

```bash
cd agent_service
source .venv/bin/activate
pip install -r requirements.txt
python -m agent_service.service
```
