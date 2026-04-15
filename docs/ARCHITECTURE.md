# AgenticFlow — Architecture

> Document version: 1.0 · Companion to `SPECIFICATION.md`

This document describes **how** AgenticFlow is built: its layers, data flow, and the contracts between components. Every non-trivial design decision is captured here (or in an ADR if we add one later).

---

## 1. System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                        Browser (React SPA)                       │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────────┐  │
│  │ Sidebar     │  │ Canvas       │  │ Chat / Config Panel     │  │
│  │ (palette,   │  │ (React Flow) │  │ (agent, node configs)   │  │
│  │  pages)     │  │              │  │                         │  │
│  └─────────────┘  └──────────────┘  └─────────────────────────┘  │
│              Zustand store  +  TanStack Query cache              │
└──────────────────────────────────────────────────────────────────┘
                                │ REST (JSON)
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                    FastAPI app (single process)                  │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌─────────────┐   │
│  │ Routers  │→ │ Services │→ │ Engine       │→ │ Node        │   │
│  │ (HTTP)   │  │ (domain) │  │ (DAG runner) │  │ Registry    │   │
│  └──────────┘  └──────────┘  └──────────────┘  └─────────────┘   │
│        │            │                │                │          │
│        └────────────┴─────┬──────────┴────────────────┘          │
│                           ▼                                      │
│                   ┌─────────────────┐                            │
│                   │ SQLAlchemy ORM  │ → SQLite file              │
│                   └─────────────────┘                            │
│                                                                  │
│  ┌──────────────────┐   ┌───────────────────┐                    │
│  │ APScheduler      │   │ TicimaxClient     │                    │
│  │ (AsyncIO, in-    │   │ (zeep, per-site   │                    │
│  │  process jobs)   │   │  cached)          │                    │
│  └──────────────────┘   └───────────────────┘                    │
│                                                                  │
│  ┌──────────────────┐                                            │
│  │ LLM abstraction  │ ── Anthropic SDK / Anthropic CLI / Gemini  │
│  └──────────────────┘                                            │
└──────────────────────────────────────────────────────────────────┘
```

**One process, one DB file, one event loop.** Simplicity is a feature.

---

## 2. Backend Layers

### 2.1 Router layer (`app/routers/`)
Thin HTTP adapters. **No business logic.** Each router:
- Parses request into a Pydantic schema (`app/schemas/`).
- Calls into a **service** or directly the **engine**.
- Returns a Pydantic response.
- Owns HTTP concerns only: status codes, pagination, filter query params.

Routers: `sites`, `workflows`, `nodes`, `executions`, `agent`, `settings`, `support`.

### 2.2 Service layer (`app/services/`)
Domain logic that spans multiple models or talks to external systems.
- `crypto_service` — Fernet encrypt/decrypt of `uye_kodu`.
- `ticimax_service` — per-site `TicimaxClient` cache; all SOAP calls go through it.
- `scheduler_service` — APScheduler singleton, job registration from workflow triggers.
- `agent_service` — wraps `llm/` to produce graph JSON from prompts.
- `settings_service` — global app settings persisted in `app_settings`.
- `llm/` — provider abstraction: `anthropic_api`, `anthropic_cli`, `google_genai`.

### 2.3 Engine layer (`app/engine/`)
Pure orchestration; knows nothing about Ticimax or HTTP.
- `node_base.BaseNode` — the contract all nodes implement.
- `context.ExecutionContext` — per-execution state: outputs map, site, DB session, trigger input.
- `executor.WorkflowExecutor` — topological sort + sequential run + template substitution.
- `errors.GraphError`, `NodeError` — engine-level exceptions.

### 2.4 Nodes (`app/nodes/`)
Every unit of work. Categorized directories:
- `triggers/` — `manual`, `schedule`, `polling`.
- `ticimax/` — hand-written hot paths + `_auto_generated.py` for the 237-op catalog.
- `transform/` — pure data ops: `filter`, `map`, `aggregate`, `parse_stok`, `only_new`.
- `logic/` — `if_condition`, `switch`, `loop`.
- `ai/` — `prompt`, `classify`, `extract`, `vision`, `vision_batch`.
- `output/` — `csv_export`, `excel_export`, `json_export`, `log`.
- `__init__.py` builds `NODE_REGISTRY: dict[type_id, BaseNode subclass]`.

### 2.5 Models (`app/models/`)
SQLAlchemy 2.x declarative mapped models.
- `Site` — `(id, name, domain, uye_kodu_encrypted)`.
- `Workflow` — `(id, name, description, site_id, graph_json, is_active, …)`.
- `Execution`, `ExecutionStep` — with `status ∈ {PENDING, RUNNING, SUCCESS, ERROR, CANCELLED, SKIPPED}` and `trigger_type ∈ {MANUAL, SCHEDULE, POLLING, AGENT}`.
- `PollingSnapshot` — per `(workflow_id, node_id)` last-seen IDs for `transform.only_new`.
- `Chat`, `AppSetting` — agent conversation + global settings.

### 2.6 Schemas (`app/schemas/`)
Pydantic v2 request/response types. One schema file per router. Models never leak through — always serialize via schemas.

---

## 3. Data Flow: Running a Workflow

```
UI "Run" click
   │
   ▼
POST /api/workflows/{id}/run
   │
   ▼
router creates Execution(status=PENDING) and returns id immediately
   │
   ▼
BackgroundTask: WorkflowExecutor.run_existing(execution_id)
   │
   ▼
_execute_graph():
   ├─ promote PENDING → RUNNING
   ├─ build ExecutionContext (site, DB, trigger_input)
   ├─ topological_sort(nodes, edges)
   │
   ├─ for each node in order:
   │    ├─ if all parents SKIPPED → mark SKIPPED, continue
   │    ├─ resolve template exprs in node config against context
   │    ├─ create ExecutionStep(RUNNING)
   │    ├─ await node.execute(context, parent_outputs, config)
   │    ├─ context.set_node_output(node_id, output)
   │    ├─ ExecutionStep → SUCCESS / ERROR
   │    └─ on ERROR: execution.status = ERROR; break
   │
   └─ set execution.status = SUCCESS/ERROR, finished_at = now
```

Per-step commits mean a crash leaves partial-but-consistent history. No retries at engine level in v1.x (nodes may implement their own).

---

## 4. Triggers & Scheduling

### 4.1 Manual
- `POST /api/workflows/{id}/run` kicks an async task.
- Returns `execution_id` immediately; UI polls `GET /api/executions/{id}`.

### 4.2 Schedule (Cron)
- Node type `trigger.schedule` with `cron` config (`0 6 * * *`).
- On workflow `is_active = true`, `SchedulerService.register_workflow(wf)` walks the graph, finds schedule nodes, and registers them with APScheduler using `CronTrigger`.
- Job ID: `wf{workflow_id}:{node_id}`.
- Job callback opens a fresh DB session, loads the workflow, runs the executor with `trigger_type=SCHEDULE`.

### 4.3 Polling
- Node type `trigger.polling` with `interval_seconds`.
- Uses `IntervalTrigger`.
- Followed by `transform.only_new` that diffs against `polling_snapshots`.
- First run: does **not** emit (thundering-herd protection); override with `emit_on_first_run: true`.

### 4.4 Agent
- `trigger_type=AGENT` records executions kicked off by the chat panel.

### 4.5 Scheduler Lifecycle
- Started on FastAPI `lifespan` startup: `scheduler_service.start()` + `refresh_all()`.
- `refresh_all()` wipes existing jobs and reinstates from DB — safe to call anytime.
- Shut down on FastAPI shutdown.

---

## 5. Template Substitution

Config values may contain `{{node_id.path}}` expressions.

- Before each node's `execute()`, the executor walks the resolved `config` (dict) and substitutes every string that matches the grammar.
- Strings that are **exactly** a single expression (e.g. `"{{n1.result}}"`) are replaced with the raw value (may be a dict/list/number).
- Strings that contain expressions as substrings (e.g. `"Merhaba {{n1.name}}"`) are interpolated as strings.
- Missing paths → `None`. Nodes decide how to treat `None`.

Grammar:
```
{{ <node_id> . <field> ( . <field> | [ <int> ] )* }}
```

---

## 6. Ticimax SOAP Integration

- `TicimaxClient` wraps `zeep` with a **factory-namespace fix** (Ticimax WSDLs omit namespaces that zeep expects). Fix lives in `app/utils/zeep_helpers.py`.
- `TicimaxService` caches one client per `site_id` (LRU); clients are recreated on site update.
- The auto-generated node catalog (`app/nodes/ticimax/_auto_generated.py`) is produced by `scripts/generate_node_catalog.py`, which AST-parses `server.py` (Ticimax's own reference client) and emits one node class per SOAP operation.
- Hot paths (e.g. `urun.select`, `siparis.list`, `set_siparis_durum_batch`, `update_ozel_alan_1_batch`) are hand-written to add domain-specific config, pagination, and output shaping.

---

## 7. LLM Abstraction

```
app/services/llm/
├── __init__.py           # get_agent_llm(), get_node_llm()
├── base.py               # LLMProvider Protocol
├── anthropic_api.py      # anthropic SDK
├── anthropic_cli.py      # subprocess → `claude` CLI (subscription mode)
└── google_genai.py       # google-genai SDK
```

Two separate factories:
- `get_agent_llm()` returns a capable, slow, expensive model (Claude Opus / Gemini Pro). Used by the agent chat to produce graphs.
- `get_node_llm()` returns a fast, cheap model (Claude Sonnet / Gemini Flash). Used by `ai.prompt`, `ai.classify`, `ai.extract` inside workflows.

Provider switch via `LLM_PROVIDER` env.

---

## 8. Frontend Architecture

### 8.1 Structure
```
frontend/src/
├── api/              # axios + TanStack Query wrappers, one file per domain
├── components/
│   ├── Canvas/       # React Flow nodes, edges, palette
│   ├── Chat/         # Agent chat panel
│   ├── ExecutionLog/ # Step-by-step JSON viewer
│   └── common/       # Buttons, dialogs, table, etc.
├── pages/            # Route-level: Dashboard, Sites, WorkflowList, WorkflowEditor, ExecutionHistory, ExecutionDetail, Settings, SupportAgent
├── store/            # Zustand: workflowStore (canvas draft state)
├── styles/           # Tailwind entry
└── types/            # Shared TS types (aligned with backend schemas)
```

### 8.2 State ownership
- **Server state** (workflows, executions, nodes catalog) → **TanStack Query** cache. One source of truth, automatic invalidation.
- **Canvas draft state** (positions, unsaved edges) → **Zustand**. Reset on route change or save.
- **URL state** (filters, pagination) → React Router query params, hydrated into page components.

### 8.3 Config panel
Reads the selected node's `config_schema` from the nodes catalog and renders inputs accordingly:
- `type: string` → text input (with template-expression helper).
- `enum` → select.
- `type: boolean` → switch.
- `type: number` → number input.
- Nested objects → collapsible sub-panel.

---

## 9. Security Model (v1.x)

- **Assumption:** the app sits behind a reverse proxy or on a private network. No built-in auth.
- Secrets (`uye_kodu`, LLM API keys) never leave the server; they are redacted from logs and execution step data.
- `MASTER_KEY` is required at startup; app refuses to boot without it.
- Fernet token rotation procedure is documented in `SECURITY.md`.

v1.1 plans to add an optional API-key middleware (header-based) for users who want to expose the UI beyond localhost.

---

## 10. Extension Points

### 10.1 Adding a new node
1. Create a file under `app/nodes/<category>/<name>.py`.
2. Subclass `BaseNode`, fill in class attributes, implement `async def execute()`.
3. Export from the category's `__init__.py`.
4. Add a unit test.
5. (Optional) Add a matching icon/color in the frontend palette.

### 10.2 Adding a new trigger type
1. Define a new `type_id` under `app/nodes/triggers/`.
2. Extend `SchedulerService` (or create a sibling service) to register jobs for it.
3. Add `TriggerType` enum value in `app/models/execution.py`.
4. Migrate DB.

### 10.3 Adding a new e-commerce platform (future)
1. Create `app/services/<platform>_service.py` mirroring `ticimax_service` shape.
2. Add encrypted credentials column(s) to `Site` **or** introduce a `PlatformAccount` model — decision deferred to the first non-Ticimax PR.
3. Add `app/nodes/<platform>/` category.
4. Update `docs/SPECIFICATION.md` platform coverage table.

---

## 11. What's NOT in this architecture (intentionally)

- No Celery / RQ / Arq — APScheduler in-process is enough for single-tenant.
- No Redis — SQLite holds scheduler state via APScheduler's SQLAlchemyJobStore (planned in v0.6).
- No WebSockets — execution progress is polled; future SSE could change this.
- No React Suspense data fetching — TanStack Query is pragmatic and explicit.
- No monorepo tooling (Nx/Turborepo) — two packages, `backend/` and `frontend/`, are independent.
