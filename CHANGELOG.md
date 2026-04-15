# Changelog

All notable changes to AgenticFlow are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Unreleased entries are added to `## [Unreleased]`. On release, rename to the version and add a new `## [Unreleased]` block at the top.

---

## [Unreleased]

### Added
- `docs/SPECIFICATION.md` — authoritative feature list, quality gates, and non-goals.
- `docs/ARCHITECTURE.md` — layered system design, data flow, extension points.
- `docs/IMPLEMENTATION.md` — rationale behind concrete code decisions.
- `docs/TASKS.md` — retro + roadmap, living checklist.
- `SECURITY.md`, `CONTRIBUTING.md`, `llms.txt`, `docs/prompt.md`.
- `.env.example`, `LICENSE` (MIT).
- README badges + doc index.

### Changed
- README restructured with feature → install → usage → docs-index flow.

### Upcoming (tracked in `docs/TASKS.md`)
- `pyproject.toml` with ruff + mypy + pytest.
- Frontend ESLint flat config + Prettier + vitest.
- `.github/workflows/ci.yml` (backend + frontend + audit).
- Root debug-script cleanup; migrate `_test_*.py`, `_debug_*.py` to `backend/tests/` and `backend/scripts/debug/`.

---

## [0.5.0] — Faz 5: Export & DX

### Added
- `output.excel_export` node (openpyxl) with `source_field` config.
- `output.json_export` node.
- `scripts/seed_db.py` — provisions 3 demo workflows (OzelAlan1 update, daily order report, ticket classification).
- `BASLAT.bat` Windows launcher with numbered menu.
- `create_shortcut.bat` to place a desktop shortcut.
- `docs/USAGE.md` end-user guide.

### Changed
- Execution artifacts served via `/api/executions/{id}/artifacts/{filename}`.

---

## [0.4.0] — Faz 4: Triggers & Observability

### Added
- `trigger.schedule` node with APScheduler cron trigger.
- `trigger.polling` node with interval trigger.
- `transform.only_new` node + `polling_snapshots` table for diff-based emission (thundering-herd guard, `emit_on_first_run` override).
- `SchedulerService` singleton with `refresh_all()` at startup.
- Execution history page: filter by status, trigger type, workflow name, error substring, date range.
- Per-execution drill-down view with step input / output / duration.

### Changed
- `Execution` + `ExecutionStep` models extended with `trigger_type`, `duration_ms`.

---

## [0.3.0] — Faz 3: Async Executor + AI

### Added
- `WorkflowExecutor` with topological sort + sequential async execution.
- `ExecutionContext` with node-output map and template substitution (`{{node_id.field.path}}`).
- `SKIPPED` status + branch collapse for skipped parents.
- AI nodes: `ai.prompt`, `ai.classify`, `ai.extract`, `ai.vision`, `ai.vision_batch`.
- Agent chat panel — natural-language → workflow graph via Claude Opus / Gemini Pro.
- LLM provider abstraction: `anthropic_api`, `anthropic_cli` (subscription mode via Claude Code binary), `google_genai`.
- Background-task execution with early `execution_id` return from `/run`.

---

## [0.2.0] — Faz 2: Node Catalog

### Added
- `BaseNode` abstract class + `NODE_REGISTRY`.
- `scripts/generate_node_catalog.py` — AST parse of Ticimax `server.py` → auto-generated node classes.
- 237 Ticimax SOAP operations exposed as nodes.
- Hand-optimized nodes: `ticimax.urun.select`, `ticimax.siparis.list`, `set_siparis_durum_batch`, `update_ozel_alan_1_batch`, `update_aciklama_batch`.
- Zeep factory-namespace fix (`app/utils/zeep_helpers.py`) for Ticimax WSDL quirks.
- `TicimaxService` with per-site client cache.
- `GET /api/nodes` catalog endpoint with full config schemas.

---

## [0.1.0] — Faz 1: Core Skeleton

### Added
- FastAPI app with CORS, lifespan, and routers: `sites`, `workflows`, `nodes`, `executions`.
- SQLAlchemy 2.x models: `Site`, `Workflow`, `Execution`, `ExecutionStep`.
- Fernet-encrypted `uye_kodu` via `crypto_service`.
- React 18 + TypeScript + Vite frontend.
- React Flow canvas with node palette, edges, config panel.
- Zustand store for canvas draft state; TanStack Query for server data.
- Five core nodes: `trigger.manual`, `transform.filter`, `transform.map`, `output.log`, `output.csv_export`.
- SQLite bootstrap via `Base.metadata.create_all` (Alembic wired but minimal).

---

[Unreleased]: https://github.com/burakdegirmenci/agenticflow/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/burakdegirmenci/agenticflow/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/burakdegirmenci/agenticflow/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/burakdegirmenci/agenticflow/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/burakdegirmenci/agenticflow/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/burakdegirmenci/agenticflow/releases/tag/v0.1.0
