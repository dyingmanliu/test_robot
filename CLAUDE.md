# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mobile device test automation platform with a Web UI (Vue + FastAPI). **Digital robots** are grouped by **business role** in the marketplace: **test analysis** (case generation, no device) vs **test execution** (runs cases on real devices). The **test execution** role is implemented by **two technical routes** today—**AutoGLM** (`autoglm_phone_tech`, in-process Python) and **Midscene** (`midscene_tech`, subprocess + visual model)—selected per robot instance via `test_agent_backend` × `device_platform`. **Test analysis** maps to `agent_service/analysis_agent/` (facade) + `agent_service/langchain_platform/` (LangChain 1.x: `CaseGenChain`, `ExploreOrchestratorGraph`). **Test execution** orchestration uses `FuncDispatchGraph` → `AutoglmExecGraph` | `MidsceneExecGraph`. Call-flow docs: `ARCHITECTURE.md` §1.3.1, `agent_service/langchain_platform/README.md`.

**agent_service** was extracted into an **independent FastAPI web service** (port 8100). The web backend calls it via HTTP (`agent_service_client.py`) instead of direct Python import. Each service has its own `.env`: `web/backend/.env` (database, JWT, logging) and `agent_service/.env` (LLM keys, model config). No root `.env`.

Test cases use a **structured format only** (steps JSON + task text). Midscene execution uses natural language mode; AutoGLM uses the same task text. YAML format has been removed from the web layer. Key env vars: `PHONE_AGENT_TIMEOUT_SEC` (default 120), `DEVICE_SCREEN_MAX_WIDTH` (default 720), `DEVICE_SCREEN_JPEG_QUALITY` (default 75). Device discovery has a 3s TTL cache. `MIDSCENE_REPLANNING_CYCLE_LIMIT` and `MIDSCENE_STEP_TIMEOUT_SEC` are injected by agent_service runtime (defaults 100/180).

**Agentic RAG knowledge base** (Web `:8000`): MySQL metadata + **Qdrant** vectors + DashScope `text-embedding-v3` embedding; ingest/query in `web/backend/app/knowledge/`. Standard/strategy uploads require **platform_admin** review before vectors are written. Agent calls `POST /api/internal/knowledge/query` via LangGraph Tools. Local: `docker compose up -d mysql qdrant`. See `ARCHITECTURE.md` §4.8.

## Development Commands

### Web Backend (FastAPI / Python)
```bash
cd web/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# MySQL + Qdrant (recommended): from repo root
docker compose up -d mysql qdrant
# Configure web/backend/.env:
# DATABASE_URL=mysql+pymysql://tcm:tcm@127.0.0.1:3306/tcm?charset=utf8mb4
# QDRANT_URL=http://127.0.0.1:6333
# KB_EMBEDDING_API_KEY=...  (DashScope / 百炼)

PYTHONPATH=. uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level info
```
- Swagger docs at http://127.0.0.1:8000/docs
- No test suite or linter configured

### Agent Service (FastAPI / Python)
```bash
cd agent_service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Configure agent_service/.env with LLM keys and model settings
python -m agent_service.service
# or: uvicorn agent_service.service.app:app --host 0.0.0.0 --port 8100
```
- Health: `GET http://127.0.0.1:8100/api/agent/health`

### Web Frontend (Vue 3 / Vite)
```bash
cd web/frontend
npm install
npm run dev          # dev server on :5173, proxies /api to :8000
npm run build        # production build
```
- No linter or formatter configured
- Frontend is plain JavaScript (no TypeScript)

### Midscene Agent (TypeScript)
```bash
cd midscene_tech
npm install
npm run task -- "task description"     # CLI execution
npm run typecheck                       # tsc --noEmit
```

### AutoGLM Agent (Python)
```bash
pip install -r requirements.txt
python -m agent_service.func_agent.cli "task description"
python -m agent_service.func_agent.cli --device-type hdc "task for HarmonyOS"
```

## Architecture

### Services (3 processes)

| Service | Port | Config | Notes |
|---------|------|--------|-------|
| Frontend (Vite) | 5173 | — | dev proxy /api → :8000 |
| Web Backend (FastAPI) | 8000 | `web/backend/.env` | DB, JWT, admin, **knowledge ingest/query**; calls agent_service via HTTP |
| Agent Service (FastAPI) | 8100 | `agent_service/.env` | LLM, device execution; SSE for long tasks |
| Qdrant | 6333 | `QDRANT_URL` in web `.env` | Vector store for knowledge base; Dashboard at :6333/dashboard |
| MySQL | 3306 | `DATABASE_URL` | Relational metadata + chunk text |

### Agent Service HTTP API

agent_service exposes REST + SSE endpoints consumed by the web backend:

| Interface | Method | Purpose |
|-----------|--------|---------|
| `/api/agent/health` | GET | Health check |
| `/api/agent/analysis/generate-case-draft` | POST | Case generation (sync) |
| `/api/agent/config/case-generation` | GET | KB config query |
| `/api/agent/func-agent/dispatch` | POST | Submit test execution task (async) |
| `/api/agent/func-agent/dispatch/{id}/stream` | GET | SSE stream: step/line/usage/done events |
| `/api/agent/func-agent/dispatch/{id}` | DELETE | Cancel execution |
| `/api/agent/explore/run` | POST | Submit feature explore (async) |
| `/api/agent/explore/run/{id}/stream` | GET | SSE stream for explore |
| `/api/agent/explore/run/{id}` | DELETE | Cancel explore |
| `/api/agent/midscene/task` | POST | Submit midscene direct task (async) |
| `/api/agent/midscene/task/{id}/stream` | GET | SSE stream for midscene |
| `/api/agent/midscene/task/{id}` | DELETE | Cancel midscene task |
| `/api/agent/tree/sync-giic` | POST | Normalize feature tree |
| `/api/agent/tree/build-function-tree` | POST | Build function tree from features |

### Test execution: backend routes × device platform

For **test execution** robot instances, each instance combines **`test_agent_backend`** (`autoglm` | `midscene`) with **`device_platform`** (`android` | `harmonyos`). The web backend submits tasks to agent_service via HTTP (`submit_func_agent_dispatch` → SSE stream), and agent_service internally routes to AutoGLM (in-process) or Midscene (subprocess).

### Directory Layout

```
agent_service/
  service/                    # NEW: FastAPI web service
    app.py                    #   FastAPI app, lifespan, router mounting
    __main__.py               #   python -m agent_service.service
    task_manager.py           #   in-memory task registry (SSE push + cancel)
    schemas.py                #   Pydantic request/response models
    sse.py                    #   SSE event formatting helper
    config.py                 #   service-level config (host, port)
    routers/                  #   health, analysis, func_agent, explore, midscene, tree
  common/
    device_resolve.py         #   resolve_execution_device_id (removes circular dep)
  func_agent/cli.py           # Functional test CLI entrypoint
  analysis_agent/             # Test analysis facade → langchain_platform
  langchain_platform/         # LangChain 1.x: chains, graphs, retrievers, tools
  requirements.txt            # agent_service dependencies (langchain-core/openai/graph)
autoglm_phone_tech/           # Test execution · AutoGLM route (LLM-driven device automation)
  model/client.py             #   model client/resources
  device/device_factory.py    #   AdbBridge / HdcBridge abstraction
  actions/handler.py          #   action dispatch
midscene_tech/                # Test execution · Midscene route (visual-driven automation)
  src/cli.ts                  #   CLI + --web-dispatch mode
  src/agent.ts                #   MidsceneTestAgent
  src/yaml_runner.ts          #   YAML test case runner
docker-compose.yml             # Local MySQL 8 + Qdrant (docker compose up -d mysql qdrant)
web/
  backend/app/
    knowledge/                # Agentic RAG: ingestion, index/pipeline, query/service
    main.py                   # FastAPI app, loads .env from web/backend/
    models.py                 # SQLAlchemy ORM (LongText → LONGTEXT on MySQL)
    database.py               # DATABASE_URL, MySQL engine, ensure_schema() migrations
    executor.py               # test execution orchestrator (HTTP → agent_service)
    rbac.py                   # role definitions (platform_admin, tse, enterprise)
    routers/                  # API route modules
    services/                 # business logic
      agent_service_client.py # HTTP client for agent_service (replaces direct import)
      case_generation.py      # Web bridge → agent_service HTTP (+ case_kb RAG)
      routers/internal_knowledge.py  # Bearer WEB_SERVICE_TOKEN KB for agent retriever
      case_agent_text.py      # structured fields → agent task text
      case_kb.py              # case KB search for RAG
  frontend/src/
    api/client.js             # Axios instance with JWT interceptors
    router/                   # Vue Router with auth + role guards
    stores/auth.js            # Pinia auth store
    views/                    # page components
    components/               # reusable components
```

### Key Architectural Details

- **Database**: **MySQL 8** via required `DATABASE_URL` / `TCM_DATABASE_URL` (PyMySQL). Local: `docker compose up -d mysql qdrant`. External CLI: `mysql -h 127.0.0.1 -P 3306 -u tcm -ptcm tcm` (must use TCP host; bare `mysql -u root` fails with socket error). Large text columns use `LongText` (MySQL `LONGTEXT`). No Alembic — schema changes use `database.ensure_schema()`. Health: `GET /api/health` returns `database: mysql`.
- **Knowledge base**: **Qdrant** (`QDRANT_URL`, default `:6333`) for vectors; MySQL for `knowledge_*` tables. Embedding via DashScope `text-embedding-v3` (`KB_EMBEDDING_*`). Ingest in `pipeline.py`; search via `knowledge_search()` with `KB_SEARCH_MIN_SCORE`. Chunk policy: env → `project_knowledge_settings.chunk_policy_json` → `knowledge_documents.chunk_policy_json` (`chunk_policy.py`). Only `active` + `indexed` chunks are retrievable. **Only upload + `standard`/`strategy`** require platform_admin review before embedding; other doc types go `active` directly.
- **Auth**: JWT (python-jose) + bcrypt. Three roles: `platform_admin`, `tse`, `enterprise`.
- **Multi-tenancy**: Projects/test cases scoped by `owner_id`. Company-level sharing via `Company.share_projects_cases_internally`.
- **Environment**: Split per service: `web/backend/.env` (DB, JWT, logging, admin, AGENT_SERVICE_URL) and `agent_service/.env` (LLM keys, model config, CASE_GEN_*, PHONE_AGENT_*, MIDSCENE_*). Each service loads its own `.env`. See `.env.example` for full reference.
- **agent_service communication**: Web backend calls agent_service via HTTP (`agent_service_client.py`). Short tasks use sync POST/GET. Long tasks (test execution, feature explore) use POST to submit → SSE stream for progress → DELETE to cancel. No more direct Python import of `agent_service/`. Cancel is immediate: `signal_cancel()` sends DELETE to agent_service via `_run_task_ids` mapping, terminating the subprocess and closing the SSE stream.
- **Test case format**: Structured only (steps JSON + task_text). Midscene execution uses natural language mode (`execution_mode: "natural"`) which auto-converts structured steps. `case_format_convert.py` and `case_yaml.py` have been removed.
- **Agent optimization**: AutoGLM model calls have 120s timeout (`PHONE_AGENT_TIMEOUT_SEC`). Screenshots scaled to 720p JPEG (quality 75). Fixed action delays reduced by ~40%. Virtual keypad input hints embedded in task text. Device discovery cached for 3s. Midscene replanning cycle limit defaults to 100, step timeout to 180s.

### Ports

| Service | Port | Notes |
|---------|------|-------|
| Frontend | 5173 | Vite dev server |
| Backend | 8000 | Uvicorn/FastAPI |
| Agent Service | 8100 | agent_service Web 服务 |
| Qdrant | 6333 | 知识库向量；Dashboard http://127.0.0.1:6333/dashboard |
| API docs | 8000/docs | OpenAPI/Swagger |
| Agent docs | 8100/docs | agent_service OpenAPI/Swagger |
| Health | 8000/api/health | Web backend |
| Agent Health | 8100/api/agent/health | Agent service |
| WebSocket | 8000/api/ws/monitor/robots | Real-time device monitoring |

## Documentation Conventions

- Business features/API changes → update `README.md`
- Architecture details → update `ARCHITECTURE.md`
- New environment variables → add to root `.env.example` (single reference) and the service’s `.env` (`web/backend/.env` or `agent_service/.env`)
- Device-layer changes → update the respective agent's `README.md`
