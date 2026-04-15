# Changelog

All notable changes to AgenticFlow are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Unreleased entries are added to `## [Unreleased]`. On release, rename to the version and add a new `## [Unreleased]` block at the top.

---

## [Unreleased]

### Added

**Sprint 7 — Operational Resilience**
- `app/startup_recovery.py` — `reconcile_interrupted_executions()` wired into the lifespan; marks any `PENDING`/`RUNNING` Execution + ExecutionStep left by a hard crash (SIGKILL / OOM / power loss) as `ERROR` with "Interrupted by process restart". 5 s grace window protects just-dispatched background tasks.
- `GET /ready` readiness probe (DB `SELECT 1` + scheduler `is_started()`), 200 / 503 with per-check breakdown. Complements the unchanged `/health` liveness probe.
- `SchedulerService.is_started()` helper.
- 46 new tests: `test_startup_recovery.py` (7), `test_scheduler_service.py` (20, async-scoped for `AsyncIOScheduler`), `test_ticimax_oa1_batch.py` (17 — `_extract_first_stok_kodu` + dry-run path), 2 extra `/ready` smoke tests.
- Coverage ratchet: backend `fail_under` 45 → 50 (actual 52.9%).

**Sprint 6 — Prod Readiness**
- `backend/Dockerfile` (multistage builder venv → `python:3.12-slim`), `frontend/Dockerfile` (multistage Node 22 build → `nginx:1.27-alpine`).
- `docker-compose.yml` for the full self-hosted stack (backend + frontend + mounted `./data`, `./logs`, `./backend/exports`).
- `frontend/nginx.conf` — SPA fallback, `/assets/*` immutable cache, `/api` + `/metrics` + `/health` reverse-proxy, security headers, gzip.
- Alembic bootstrap: `alembic/env.py` wired to `app.config.get_settings().DATABASE_URL` + `Base.metadata`; batch-mode for SQLite; baseline migration `cd868abd5d6d` creates all 8 tables.
- `docs/MIGRATIONS.md` — authoring workflow, SQLite sharp edges, deploy flow, disaster recovery, revision history.
- `docs/DEPLOYMENT.md` — quickstart, env reference, reverse-proxy recipes (Traefik / Caddy / nginx), auth options, backup runbook, Prometheus scrape, upgrade + housekeeping.
- Optional `X-Api-Key` middleware (`app/middleware/api_key.py`, new `API_KEY` env) with open-paths allowlist + constant-time comparison; 10 new integration tests.
- `.env.example` expanded with Sprint 5 / 6 variables.

**Sprint 5 — Observability**
- `app/logging_config.py` (structured JSON logs via `python-json-logger`, rotating file, secret-key redaction filter).
- `app/middleware/logging.py` (HTTP request log with method / path / status / duration / request_id; X-Request-ID echo).
- `app/metrics.py` + `GET /metrics` (Prometheus text exposition; `agenticflow_requests_total`, `agenticflow_executions_total`, `agenticflow_execution_steps_total`).
- Executor instrumentation (`execution_finished`, `execution_step_failed` log records + metric increments).
- Optional Sentry via `SENTRY_DSN` env + `[project.optional-dependencies] sentry` extra.
- `docs/SPECIFICATION.md`, `docs/ARCHITECTURE.md`, `docs/IMPLEMENTATION.md`, `docs/TASKS.md`, `docs/prompt.md`, `CHANGELOG.md`, `SECURITY.md`, `CONTRIBUTING.md`, `llms.txt`, `LICENSE`, initial `.env.example` — Sprint 0.
- Full discipline toolchain: `backend/pyproject.toml`, `frontend/eslint.config.js`, `.prettierrc.json`, `vitest.config.ts`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `.github/dependabot.yml`, PR + issue templates, CODEOWNERS.
- README badges + doc index.

### Changed

- **Backend database**: SQLite connections now apply `PRAGMA journal_mode = WAL`, `synchronous = NORMAL`, `foreign_keys = ON`, `busy_timeout = 5000` on every new connection (Sprint 6).
- **Middleware order**: request → CORS → ApiKey → request-log → route (Sprint 6).
- **FastAPI middleware stack** gains structured logging + optional API-key gate (Sprint 5 + 6).
- **Type safety**: `datetime.utcnow()` (deprecated on Python 3.12) replaced with a `utcnow()` helper across 14 call sites + 10 model defaults (Sprint 5).
- **MyPy**: strict-adjacent baseline is now a required CI gate; 18 existing errors fixed (unused ignores, unreachable code, missing awaits, generator return types, Optional-assignment dance in `routers/agent.py`, `llm/base.py stream()` signature) (Sprint 5).
- **Ruff lint**: ratchet plan documented; current rule set is `E, W, F, I, B, SIM, UP`.
- **Coverage thresholds**: backend `fail_under` 0 → 20 → 35 → 45 across Sprints; frontend 0 → 2 → 5 (lines); steady ratchet as new tests land.
- **README** restructured with feature → install → docs-index flow; CI + style badges added.

### Removed

- Root `_test_*.py`, `_debug_*.py`, `_ui_test_*.py`, `_smoke_test_*.py` scripts migrated into `backend/scripts/debug/` and `backend/scripts/legacy_scripts/` (Sprint 1).
- `backend/app/nodes/ticimax/_auto_generated.py` is now tracked (was gitignored) so tests + CI can resolve the 237 SOAP node classes without running the generator (Sprint 3 hotfix).
- Pytest `datetime.utcnow` deprecation filter — fixed at the source (Sprint 5).

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
