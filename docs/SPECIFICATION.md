# AgenticFlow — Specification

> Document version: 1.0 · Status: Authoritative · Last updated: 2026-04-15

This document is the single source of truth for what AgenticFlow **is**, what it **is not**, and the **quality bar** every change must respect.

---

## 1. Project Identity

| Field | Value |
|---|---|
| **Name** | AgenticFlow |
| **Version** | 0.5.x (toward 1.0) |
| **License** | MIT |
| **Author** | Burak Değirmenci |
| **Scope** | Self-hosted, single-tenant automation platform for Ticimax e-commerce merchants |
| **Homepage** | github.com/burakdegirmenci/agenticflow |
| **Primary users** | Ticimax merchants, automation tinkerers, TypeScript/Python developers |

### 1.1 One-line Pitch
> Visual node-based workflow builder + agentic AI chat that turns 237 Ticimax SOAP operations into drag-and-drop automations, triggered manually, on cron, or via polling.

---

## 2. Goals & Non-Goals

### 2.1 Goals
- **Visual first** — every automation is a graph the user can read at a glance.
- **Agentic AI native** — users describe automations in natural language; the agent produces the graph.
- **Ticimax parity** — every meaningful Ticimax SOAP operation is reachable as a node, without the user touching WSDL or XML.
- **Extensible by design** — new nodes, new trigger types, and (future) new e-commerce platform adapters can be added without touching the engine.
- **Zero-vendor-lock for the user** — self-hosted, SQLite file, exportable workflows (JSON).
- **Production-grade defaults** — secrets encrypted at rest, scheduler crash-safe, executions observable step-by-step.

### 2.2 Non-Goals (explicitly out of scope for v1.x)
- ❌ **Multi-tenant SaaS** — one install = one user/team. No user accounts, no RBAC, no billing.
- ❌ **Horizontal scaling** — single worker, sequential execution. Heavy-concurrency workloads are not a target.
- ❌ **Real-time streaming** — no Kafka/Redis Streams; polling + cron are the only triggers.
- ❌ **Low-code UI for end customers** — this is a tool for merchants/ops teams, not a "build your own store" builder.
- ❌ **Full e-commerce storefront** — AgenticFlow automates operations on top of an existing Ticimax store; it does not replace the store.
- ❌ **Custom DSL** — graphs are React Flow JSON; no YAML/Python script format.

### 2.3 Platform Coverage (v1.x)
- **Ticimax** — first-class, all 237 SOAP operations exposed.
- **Other platforms (İkas, Shopify, WooCommerce)** — adapter layer is architected for this, but no adapter ships in v1.x. Community PRs welcome post-1.0.

---

## 3. Functional Requirements

### 3.1 Site Management
- Register 1..N Ticimax sites (domain + `uye_kodu` token).
- `uye_kodu` **must** be encrypted at rest with Fernet (symmetric), key from `MASTER_KEY` env.
- Connection test button in UI must call a safe, read-only Ticimax SOAP method.
- Deleting a site cascades to its workflows and executions.

### 3.2 Workflow CRUD
- Create / rename / duplicate / delete workflows.
- Each workflow is bound to exactly one site.
- `graph_json` persists React Flow's `{nodes, edges}` structure verbatim.
- Activation toggle: `is_active=true` registers its trigger nodes with the scheduler.

### 3.3 Canvas (Frontend)
- Drag-and-drop from a categorized node palette.
- Connect nodes with edges; topological validity enforced by the backend, not the canvas.
- Per-node config panel generated from each node's `config_schema` (JSON Schema subset).
- Template expressions in config values: `{{node_id.field.path}}` resolves parent outputs at runtime.
- Save workflow = PUT `graph_json` to backend.

### 3.4 Node Catalog (237 + core)
Categories and counts:

| Category | Count | Source |
|---|---:|---|
| `trigger` | 3 | Manual, Schedule (cron), Polling |
| `ticimax` | ~237 | Auto-generated from `server.py` AST + hand-optimized hot paths |
| `transform` | 5+ | `filter`, `map`, `aggregate`, `parse_stok`, `only_new` |
| `logic` | 3 | `if_condition`, `switch`, `loop` |
| `ai` | 5 | `prompt`, `classify`, `extract`, `vision`, `vision_batch` |
| `output` | 4 | `csv_export`, `excel_export`, `json_export`, `log` |

- Every node implements `BaseNode` with `type_id`, `category`, `display_name`, `icon`, `color`, `input_schema`, `output_schema`, `config_schema`, and async `execute()`.
- Catalog endpoint `GET /api/nodes` returns metadata for all registered nodes.

### 3.5 Execution Engine
- Topological sort of the graph; cycles → `GraphError`.
- Sequential execution (single worker) in the FastAPI event loop.
- Each node's output is stored in `ExecutionContext` under its `node_id`.
- Template substitution happens **before** the node's `execute()` is called.
- A parent that ended in `SKIPPED` status does not contribute to its children's inputs; if all parents are skipped, the child is also skipped (branch collapse).
- Every node becomes one `ExecutionStep` row with status, input, output, error, duration.
- A node-level error halts the execution and marks `Execution.status = ERROR`.

### 3.6 Triggers
1. **Manual** — UI "Run" button → POST `/api/workflows/{id}/run`.
2. **Schedule** — `trigger.schedule` node with a 5-field cron expression; registered with APScheduler on workflow activation.
3. **Polling** — `trigger.polling` node with an interval (seconds); must be followed by `transform.only_new` for diff-based emission; snapshots persist in the `polling_snapshots` table.
4. **Agent** — the agent chat may kick off an ad-hoc execution (trigger type `AGENT`).

### 3.7 Agentic Chat
- Chat panel can produce a workflow graph from a natural-language request.
- Providers: **Anthropic API** (default), **Anthropic CLI** (subscription mode via Claude Code), **Google Gemini** (fallback).
- The agent's output is a graph JSON that the frontend can paste into the canvas.
- In-workflow AI nodes (`ai.prompt`, `ai.classify`, `ai.extract`, `ai.vision`) use the node model (cheap, fast); the agent uses the agent model (capable).

### 3.8 Execution History
- Filter by status, trigger type, date range, workflow name, error substring.
- Per-execution drill-down showing every step's input, output, duration, and error.
- JSON blobs in step input/output are safely serialized (long strings truncated for display, full in `/raw`).

### 3.9 Export Formats
- `output.csv_export`, `output.excel_export` (openpyxl), `output.json_export`, `output.log`.
- Files written to `backend/exports/` (gitignored); served via `GET /api/executions/{id}/artifacts/{filename}`.
- Excel export requires a list-of-dicts source; configurable via `source_field`.

### 3.10 LLM Provider Abstraction
- `app/services/llm/` exposes `get_agent_llm()` and `get_node_llm()`.
- `LLM_PROVIDER` env switches between `anthropic_api`, `anthropic_cli`, `google_genai`.
- Token/cost accounting per execution is **not** in v1.x (tracked as a roadmap item).

---

## 4. Non-Functional Requirements

### 4.1 Quality Gates (CI-enforced)
| Gate | Target |
|---|---|
| Python type check (`mypy --strict`) | 0 errors |
| Python lint (`ruff check`) | 0 errors |
| Python format (`ruff format --check`) | clean |
| Python test (`pytest`) | all green |
| Python coverage (core: engine, services, nodes sans auto-gen) | ≥ 80% |
| Python coverage (auto-generated Ticimax nodes) | smoke-only, every node reachable once |
| TypeScript (`tsc --noEmit`) | 0 errors, `any` disallowed via ESLint |
| Frontend lint (`eslint .`) | 0 errors |
| Frontend format (`prettier --check`) | clean |
| Frontend test (`vitest run`) | all green |
| Frontend coverage (non-canvas core) | ≥ 60% |

### 4.2 Performance Targets
| Metric | Target |
|---|---|
| API p95 latency (list/detail endpoints, cold DB < 10k rows) | < 200 ms |
| API p95 latency (executions list with filters) | < 400 ms |
| Engine per-node overhead (excluding node `execute()`) | < 100 ms |
| Workflow executor cold start (no SOAP calls) | < 1 s |
| Backend cold start to readiness | < 3 s |
| Cron job dispatch jitter | < 5 s |
| Scheduler memory footprint (100 active workflows) | < 150 MB RSS |
| Frontend initial bundle (gzipped) | < 500 KB |
| WorkflowEditor LCP | < 2.5 s |
| Canvas interaction (drag, connect, config-update) | < 50 ms perceived |

### 4.3 Reliability
- Scheduler must survive workflow graph errors without crashing.
- Database writes during execution are committed per-step; a crash leaves partial but consistent history.
- Polling snapshot writes are idempotent.
- A failed SOAP call does not abort the scheduler; it marks the execution `ERROR` and moves on.

### 4.4 Security
- `MASTER_KEY` is required; app refuses to start without it.
- No secrets (API keys, `uye_kodu`) ever appear in logs or execution step data.
- `.env` is gitignored; `.env.example` ships with placeholder values.
- CORS restricted to configured origins; no `*` in production.
- No built-in auth layer in v1.x (single-tenant, user is expected to front with reverse proxy / VPN / SSH tunnel); v1.1 will add optional API-key middleware.
- Dependency supply-chain: `pip-audit` + `npm audit` green before each release.

### 4.5 Observability
- Structured JSON logs (one record per HTTP request, one per scheduled job fire, one per execution step transition) — planned in v0.6.
- Log rotation via stdlib.
- Optional Sentry DSN via env — planned in v0.6.

---

## 5. Target Runtime

| Component | Minimum | Recommended |
|---|---|---|
| Python | 3.11 | 3.12 |
| Node.js | 20 LTS | 22 LTS |
| OS | Linux / macOS / Windows 10+ | Linux x64 |
| RAM | 512 MB | 1 GB |
| Disk | 200 MB + executions/exports | 2 GB |
| Browser | Chrome 120+, Firefox 120+, Edge 120+, Safari 17+ | latest |

---

## 6. Technology Decisions (authoritative)

| Concern | Choice | Rationale |
|---|---|---|
| Web framework | **FastAPI** | Async-native, Pydantic v2 integration, great OpenAPI |
| ORM | **SQLAlchemy 2.x** | Mature, async-capable, typed |
| DB | **SQLite** | Single-tenant assumption, zero-ops, easy backup |
| Migrations | **Alembic** | Canonical SQLAlchemy choice |
| Scheduler | **APScheduler** (`AsyncIOScheduler`) | In-process, no Redis, lives on FastAPI loop |
| Config | **pydantic-settings** | Typed env parsing, validation |
| SOAP | **zeep** with factory-namespace fix | Only mature Python SOAP client |
| Crypto | **cryptography** (Fernet) | Stdlib-adjacent, symmetric, simple |
| LLM SDK | **anthropic**, **google-genai** | Official SDKs; CLI path for subscription users |
| Frontend | **React 18 + TS + Vite** | Stable, fast HMR, first-class TS |
| Canvas | **@xyflow/react** | De-facto standard for node-based UIs |
| State | **Zustand** | Minimal, fits canvas needs without Redux overhead |
| Data fetching | **TanStack Query** | Cache, retry, invalidation; battle-tested |
| Styling | **Tailwind** | Utility-first, ships with Vite cleanly |
| Python tooling | **ruff** + **mypy** + **pytest** | Modern, fast, one-stop |
| Frontend tooling | **ESLint flat** + **Prettier** + **vitest** | Modern, fast, flat-config |

A change to any row requires updating this table and `docs/ARCHITECTURE.md`.

---

## 7. Out-of-the-Box Node Contract

Every node:
1. Subclasses `BaseNode`.
2. Declares `type_id` in reverse-DNS form: `{category}.{domain}.{action}` (e.g. `ticimax.urun.select`, `transform.only_new`).
3. Ships its own `config_schema` (JSON Schema subset: `type`, `properties`, `required`, `enum`, `default`, `description`).
4. Implements `async def execute(context, inputs, config) -> dict`.
5. Returns a **JSON-serializable dict**; non-serializable values cause executor to refuse commit.
6. Is registered in `app/nodes/__init__.NODE_REGISTRY`.
7. Has at least one unit test (auto-generated Ticimax nodes: smoke registration test only).

Breaking the contract = broken build.

---

## 8. Data Contracts

### 8.1 Workflow Graph (`graph_json`)
```json
{
  "nodes": [
    {
      "id": "n1",
      "type": "ticimax.urun.select",
      "position": { "x": 100, "y": 120 },
      "data": {
        "label": "Aktif ürünler",
        "config": { "aktif": true, "limit": 500 }
      }
    }
  ],
  "edges": [
    { "id": "e1-2", "source": "n1", "target": "n2" }
  ]
}
```

### 8.2 Template Expression Grammar
```
{{ <node_id> . <field> ( . <field> | [ <int> ] )* }}
```
- Resolves against `context.node_outputs[<node_id>]`.
- Missing paths → `None` (node decides whether this is an error).
- Arrays support integer index: `{{n1.result.items[0].id}}`.

---

## 9. Release & Versioning

- **SemVer**: `MAJOR.MINOR.PATCH`.
- **0.x**: breaking changes permitted in MINOR; documented in `CHANGELOG.md`.
- **1.0**: graph_json format frozen; migrations must be backward compatible.
- Every release: tag, CHANGELOG entry, docs up-to-date, CI green, `pip-audit` + `npm audit` clean.

---

## 10. Glossary

| Term | Meaning |
|---|---|
| **Workflow** | A persisted graph of nodes + edges bound to a site. |
| **Execution** | One run of a workflow; has `ExecutionStep` children. |
| **Node** | A unit of work (`BaseNode` subclass). |
| **Trigger node** | A node that causes executions to start (manual/schedule/polling). |
| **Site** | A Ticimax store (domain + encrypted `uye_kodu`). |
| **Agent** | An LLM that produces workflow graphs from natural language. |
| **Snapshot** | Polling state stored in `polling_snapshots` to emit only new items. |
