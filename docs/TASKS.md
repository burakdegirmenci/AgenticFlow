# AgenticFlow — Tasks & Roadmap

> Document version: 1.0 · Living document · Companion to `SPECIFICATION.md`

This file tracks:
1. **Retro** — what shipped (Faz 1–5).
2. **Now** — the hygiene / discipline sprints in progress.
3. **Next** — roadmap items with clear triggers for entry.

Task syntax: `- [ ]` open, `- [x]` done, `- [~]` in progress, `- [!]` blocked.

---

## Retro (Shipped)

### Faz 1 — Core Skeleton
- [x] FastAPI app + CORS + lifespan
- [x] SQLAlchemy models: Site, Workflow, Execution, ExecutionStep
- [x] React Flow canvas with palette + config panel
- [x] 5 core nodes: trigger.manual, transform.filter, transform.map, output.log, output.csv_export

### Faz 2 — Node Catalog
- [x] `BaseNode` abstract + `NODE_REGISTRY`
- [x] `scripts/generate_node_catalog.py` — AST parse `server.py` → one class per SOAP op
- [x] 237 auto-generated Ticimax nodes
- [x] Hand-optimized hot paths: `urun.select`, `siparis.list`, `set_siparis_durum_batch`, `update_ozel_alan_1_batch`, `update_aciklama_batch`
- [x] `config_schema` for every node, rendered dynamically by frontend
- [x] Zeep factory-namespace fix (`utils/zeep_helpers.py`)

### Faz 3 — Async Executor + AI
- [x] Topological sort + sequential async runner
- [x] `ExecutionContext` + template substitution (`{{node_id.path}}`)
- [x] Per-step DB commit + `ExecutionStep` status tracking
- [x] `SKIPPED` branch propagation
- [x] AI nodes: `ai.prompt`, `ai.classify`, `ai.extract`, `ai.vision`, `ai.vision_batch`
- [x] Agent chat — Claude/Gemini graph generation
- [x] LLM provider abstraction (`anthropic_api`, `anthropic_cli`, `google_genai`)

### Faz 4 — Triggers & Observability
- [x] `trigger.schedule` (APScheduler cron)
- [x] `trigger.polling` (interval)
- [x] `transform.only_new` + `polling_snapshots` diff
- [x] `SchedulerService` singleton with `refresh_all` on startup
- [x] Execution history page with status / trigger / search / date filters
- [x] Per-execution drill-down: step input/output/duration

### Faz 5 — Export & DX
- [x] `output.excel_export` (openpyxl)
- [x] `output.json_export`
- [x] `scripts/seed_db.py` — 3 demo workflows
- [x] `BASLAT.bat` Windows launcher + desktop shortcut
- [x] `docs/USAGE.md`

---

## Now — Discipline Retrofit

### Sprint 0 — Documentation Skeleton  (in progress)
- [x] `docs/SPECIFICATION.md`
- [x] `docs/ARCHITECTURE.md`
- [x] `docs/IMPLEMENTATION.md`
- [x] `docs/TASKS.md` (this file)
- [ ] `CHANGELOG.md` — retroactive v0.1 → v0.5 entries
- [ ] `SECURITY.md` — credentials, Fernet rotation, reporting
- [ ] `CONTRIBUTING.md` — PR checklist, commands, conventions
- [ ] `llms.txt` — project summary for AI assistants
- [ ] `docs/prompt.md` — onboarding prompt
- [ ] `.env.example` — all env vars from `config.py`
- [ ] `LICENSE` (MIT)
- [ ] README badges + doc links

### Sprint 1 — Python Toolchain + Cleanup
- [x] `backend/pyproject.toml` — single source of dep + tool config
- [x] Keep `requirements.txt` as a lockfile while `pyproject.toml` declares the canonical set (dual-file strategy)
- [x] Configure `ruff` (lint + format) with project rules + per-file ignores
- [x] Configure `mypy --strict` (config only — tool install pending)
- [x] Configure `pytest` + `pytest-asyncio` + `pytest-cov`
- [x] Move root clutter into proper locations:
  - Root `_test_*.py` / `_debug_*.py` / `_ui_test_*.py` → `backend/scripts/debug/` + `backend/scripts/legacy_scripts/`
  - `backend/_smoke_*`, `backend/_ui_test_*` → `backend/scripts/legacy_scripts/`
  - `_ui_test_screens/` gitignored
- [x] `backend/tests/conftest.py` with `db_session`, `site_factory`, `workflow_factory`, `fake_ticimax`, `execution_context`, `patch_ticimax_service` fixtures
- [x] First green `pytest` run: **34 tests, 0 failures, 1.39s**
  - 11 node-registry contract tests (validate all 262 nodes)
  - 7 topological sort + cycle tests
  - 8 template substitution tests
  - 4 ExecutionContext tests
  - 4 FilterNode behavior tests
- [ ] Install `mypy` in dev venv and run `mypy app` (expect findings — separate PR)
- [ ] Migrate `backend/scripts/legacy_scripts/` into real pytest integration tests (track per-file in `legacy_scripts/README.md`)

### Sprint 2 — Frontend Toolchain
- [x] `eslint.config.js` (flat config) with `@typescript-eslint` (`recommendedTypeChecked` + `stylistic`), `react`, `react-hooks`, `react-refresh`, `simple-import-sort`, `import`
- [x] `.prettierrc.json` + `.prettierignore` (with `prettier-plugin-tailwindcss`)
- [x] `tsconfig.json` tightening: `noImplicitOverride`, `noImplicitReturns`, `forceConsistentCasingInFileNames`, `allowUnreachableCode: false` (kept `noUncheckedIndexedAccess` deferred — see Sprint 4)
- [x] `vitest.config.ts` + `vitest.setup.ts` + `@testing-library/react` + `@testing-library/jest-dom` + jsdom
- [x] Baseline tests: `workflowStore` (8 tests), `apiClient` interceptor (6 tests)
- [x] New npm scripts: `lint`, `lint:fix`, `format`, `format:check`, `typecheck`, `test`, `test:watch`, `test:coverage`, `test:ui`, `ci`
- [x] Fixed 5 blocking lint errors (`api/client.ts` error typing, `NodeConfigPanel` string coercion, `MessageList` non-null assertion)
- [x] Full `npm run ci` green: prettier ✓ eslint 0-errors ✓ tsc 0-errors ✓ vitest 14/14 ✓
- [ ] Ratchet ESLint to `strictTypeChecked` once 31 existing warnings (float-promises, unsafe-*, misused-promises) are addressed — Sprint 4
- [ ] Re-enable `noUncheckedIndexedAccess` in tsconfig after indexing sites are audited — Sprint 4

### Sprint 3 — CI
- [x] `.github/workflows/ci.yml` — backend (py 3.11 + 3.12) + frontend (node 20 + 22) + audit, all in parallel
  - Concurrency cancellation per ref
  - Aggregate `ci-gate` job for single branch-protection check
  - Coverage artifact upload (backend xml, frontend lcov)
  - Vite production build as smoke test
- [x] `.github/workflows/release.yml` — on `v*.*.*` tag: build sdist + frontend bundle, extract CHANGELOG section, create GH Release with artifacts (prerelease auto-detected from `-alpha`/`-beta`/`-rc`)
- [x] `.github/dependabot.yml` — weekly (Monday 06:00 Europe/Istanbul), grouped PRs for pip + npm + github-actions, major bumps separated
- [x] `.github/pull_request_template.md` — discipline checklist (tests, docs, changelog, no secrets)
- [x] `.github/ISSUE_TEMPLATE/` — bug_report.yml, feature_request.yml, config.yml (blank issues disabled, security routed to advisory)
- [x] `.github/CODEOWNERS` — maintainer review required on all paths
- [x] README CI badge added; style badge (ruff + prettier) added
- [x] CONTRIBUTING.md — branch protection + CI + release policy documented
- [x] **CI green end-to-end** on GitHub Actions (private repo `burakdegirmenci/AgenticFlow`):
  - Backend matrix (py 3.11 + 3.12): ruff format+check, mypy (advisory), pytest (34 passed, 2s)
  - Frontend matrix (node 20 + 22): prettier, eslint, tsc, vitest (14 passed, 6s), vite build
  - Audit job: pip-audit + npm audit (advisory)
  - CI gate aggregate: pass
- [x] Shipped hotfixes found via real CI (commits after initial push):
  - `pyproject.toml` readme/license parent-path refs → SPDX string + project URLs
  - Coverage thresholds set to real baselines (backend 20%, frontend 2-45%); Sprint 4 ratchets to 80/60
  - Ruff ruleset pared to `E, W, F, I, B, SIM, UP` — PL/S/RUF/ASYNC/etc deferred
  - MyPy downgraded from `strict=true` to a targeted baseline; strict mode is a Sprint 4 goal
  - TicimaxClient import made lazy (`_load_ticimax_client()` + TicimaxClientUnavailable) so tests collect without the Claude Code skill installed
  - `backend/app/nodes/ticimax/_auto_generated.py` now tracked (237 SOAP nodes, ~430 KB) — regenerable but shipped for CI/checkout reproducibility
  - `frontend/coverage/` gitignored
- [ ] **Manual step:** configure branch protection rules on GitHub (settings documented in CONTRIBUTING.md)

### Sprint 4 — Test Coverage to Target
- [ ] Engine: `executor`, `context`, template substitution — unit
- [ ] Every node in `transform/`, `logic/`, `output/` — unit
- [ ] Top 20 Ticimax hand-written nodes — unit with `fake_ticimax`
- [ ] Auto-generated Ticimax nodes — contract test (register, metadata present)
- [ ] `SchedulerService` — integration (register / fire / unregister with `freezegun`)
- [ ] `transform.only_new` — integration (snapshot behavior)
- [ ] Frontend: store + api wrappers → 60% coverage
- [ ] CI `--cov-fail-under=80` enabled

### Sprint 5 — Observability & Logging + Code Hygiene
- [ ] Structured JSON logging via `python-json-logger`
- [ ] Log rotation (stdlib `RotatingFileHandler`)
- [ ] Request logging middleware (method, path, ms, status, request_id)
- [ ] Per-execution log record (execution_id, workflow_id, trigger, duration)
- [ ] Optional Sentry DSN via env (`SENTRY_DSN`)
- [ ] `/metrics` endpoint (plaintext counters: executions_total, scheduler_jobs, steps_failed_total)
- [ ] **Migrate `datetime.utcnow()` → `datetime.now(UTC)`** (Python 3.12 deprecation; currently filtered in pytest)

### Sprint 6 — Prod Readiness
- [ ] `Dockerfile` (multistage: builder → runtime)
- [ ] `docker-compose.yml` (backend + frontend with nginx)
- [ ] Switch Alembic to be the only DB bootstrap path
- [ ] Optional API-key middleware (header `X-Api-Key`, env `API_KEY`)
- [ ] WAL mode + short transactions (SQLite contention mitigation)
- [ ] Graceful shutdown: drain running executions, mark in-flight as ERROR on forced stop
- [ ] `docs/DEPLOYMENT.md` + `docs/MIGRATIONS.md`

---

## Next — Roadmap (Post-Retrofit)

### v1.0 — First Stable Release
Trigger: Sprints 0–6 complete, CI green on `main` for ≥ 7 days.
- [ ] Freeze `graph_json` format
- [ ] Public announcement / Show HN / Turkish dev community posts
- [ ] Example gallery (10 real-world workflows)

### v1.1 — Workflow Versioning
- [ ] `workflow_versions` table; every save creates a version
- [ ] UI diff view between versions
- [ ] Rollback button

### v1.2 — Webhook Trigger
- [ ] `trigger.webhook` node; `POST /api/webhooks/{token}` dispatches the owning workflow
- [ ] Per-workflow secret rotation
- [ ] Signature verification helper

### v1.3 — Retry & Error Policy
- [ ] Per-node retry config (max, backoff)
- [ ] `onError` branch support in graphs
- [ ] Dead-letter snapshot for repeatedly-failing polling emissions

### v1.4 — Node Marketplace
- [ ] Plugin loader for user-provided node packages (`agenticflow-node-*`)
- [ ] Signed plugin manifest
- [ ] `docs/NODE_PLUGINS.md`

### v2.0 — Multi-Platform Adapters
Trigger: community interest + at least one non-Ticimax PR.
- [ ] `PlatformAccount` model; `Site` renamed to `Account` or similar
- [ ] İkas adapter (SOAP/REST depending on their public API)
- [ ] Shopify adapter (Admin API)
- [ ] WooCommerce adapter (REST API)
- [ ] Generic platform-agnostic node taxonomy

### Someday / Maybe
- [ ] Multi-tenant mode (opt-in, with auth)
- [ ] Horizontal scaling (Arq + Redis)
- [ ] Real-time SSE execution progress
- [ ] Cost / token accounting per execution
- [ ] Local LLM support (Ollama)
- [ ] Graph lint rules (detect common anti-patterns before save)

---

## Meta

- **When a task is blocked**: annotate with `- [!]` and link to the blocker issue/PR.
- **When scope grows**: prefer to split the task into sub-tasks rather than letting it balloon.
- **When a roadmap item is discarded**: move it to a `## Rejected` section at the bottom with the reason, don't silently delete.
