# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mobile device test automation platform. It provides a web UI for managing test cases and orchestrating automated tests on Android and HarmonyOS devices through two execution engines: **AutoGLM** (Python, LLM-driven) and **Midscene** (TypeScript, visual-driven).

## Development Commands

### Web Backend (FastAPI / Python)
```bash
cd web/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level info
```
- Swagger docs at http://127.0.0.1:8000/docs
- No test suite or linter configured

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
cd midscene_agent
npm install
npm run task -- "task description"     # CLI execution
npm run typecheck                       # tsc --noEmit
```

### AutoGLM Agent (Python)
```bash
pip install -r requirements.txt
python main.py "task description"
python main.py --device-type hdc "task for HarmonyOS"
```

## Architecture

### Execution Engine x Device Platform Matrix

The central concept: each robot instance combines a **test agent backend** (`autoglm` | `midscene`) with a **device platform** (`android` | `harmonyos`), yielding 4 execution paths. Routing logic is in `web/backend/app/executor.py` and `web/backend/app/services/device_platform.py`.

- **AutoGLM** runs **in-process** — the backend imports and calls `PhoneTestAgent` directly.
- **Midscene** runs as a **subprocess** — the backend spawns `tsx src/cli.ts --web-dispatch` and communicates via stdin JSON / stdout JSON lines.

### Case Authoring Agent (`analysis_agent/`)

Separate from device execution; same in-process import pattern as `autoglm_phone_agent` in `executor.py`.

- **Package**: `analysis_agent/` — `AnalysisAgent`, `model/client.py`, `config/`, `parser.py` (LLM output is always **structured**)
- **Web bridge**: `case_generation.py` — KB + ORM → `AnalysisAgent.generate_case_draft()`; optional `case_format=yaml` → `case_format_convert.structured_to_yaml()`
- **Format convert**: `case_format_convert.py` — structured ↔ Midscene YAML; `POST /api/test-cases/convert-format` for edit-dialog switching
- **API**: `POST /api/test-cases/generate` (body: `project_id`, `robot_instance_id` for test-analysis instance, `prompt`, optional `case_format`); draft only, no DB write
- **Env**: `CASE_GEN_*` in repo root `.env` (see `analysis_agent/README.md`)
- **E2E**: Case generation (analysis robot + `generate` → save `test_cases`) is separate from **functional execution** (execution robot + `POST …/run` → `test_runs`). Full collaboration flow: README **「端到端工作流」** and `ARCHITECTURE.md` §1.4.

### Directory Layout

```
main.py                       # AutoGLM CLI entrypoint
analysis_agent/               # Python: NL → structured test case draft
autoglm_phone_agent/          # Python: LLM-driven device automation
  agent.py                    #   observe-reason-execute loop
  device_factory.py           #   AdbBridge / HdcBridge abstraction
  actions/handler.py          #   action dispatch
midscene_agent/               # TypeScript: visual-driven automation
  src/cli.ts                  #   CLI + --web-dispatch mode
  src/agent.ts                #   MidsceneTestAgent
  src/yaml_runner.ts          #   YAML test case runner
web/
  backend/app/
    main.py                   # FastAPI app, loads .env from repo root
    models.py                 # SQLAlchemy ORM models
    database.py               # SQLite setup, ensure_schema() migrations
    executor.py               # test execution orchestrator
    rbac.py                   # role definitions (platform_admin, tse, enterprise)
    routers/                  # API route modules
    services/                 # business logic
      case_generation.py      # Web bridge → analysis_agent
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

- **Database**: SQLite via SQLAlchemy 2.x. No Alembic — schema changes use `database.ensure_schema()` with `ALTER TABLE ... ADD COLUMN` and inspector checks.
- **Auth**: JWT (python-jose) + bcrypt. Three roles: `platform_admin`, `tse`, `enterprise`.
- **Multi-tenancy**: Projects/test cases scoped by `owner_id`. Company-level sharing via `Company.share_projects_cases_internally`.
- **Environment**: Single `.env` at repo root loaded by both CLI agents and the backend. Copy `.env.example` and fill in required keys.

### Ports

| Service | Port | Notes |
|---------|------|-------|
| Frontend | 5173 | Vite dev server |
| Backend | 8000 | Uvicorn/FastAPI |
| API docs | 8000/docs | OpenAPI/Swagger |
| Health | 8000/api/health | |
| WebSocket | 8000/api/ws/monitor/robots | Real-time device monitoring |

## Documentation Conventions

- Business features/API changes → update `README.md`
- Architecture details → update `ARCHITECTURE.md`
- New environment variables → add to `.env.example`
- Device-layer changes → update the respective agent's `README.md`
