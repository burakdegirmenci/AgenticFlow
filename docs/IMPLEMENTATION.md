# AgenticFlow — Implementation Notes

> Document version: 1.0 · Companion to `SPECIFICATION.md` and `ARCHITECTURE.md`

This document captures the **why** behind concrete code decisions that are not obvious from reading the source. If a choice is surprising or has plausible alternatives, it belongs here.

---

## 1. Directory Layout

```
AgenticFlow/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI entry, lifespan, CORS
│   │   ├── config.py                   # pydantic-settings
│   │   ├── database.py                 # SQLAlchemy engine + SessionLocal
│   │   ├── engine/                     # DAG orchestration (pure)
│   │   ├── nodes/                      # BaseNode implementations by category
│   │   ├── services/                   # crypto, ticimax, scheduler, agent, llm/
│   │   ├── routers/                    # HTTP adapters, no logic
│   │   ├── schemas/                    # Pydantic request/response
│   │   ├── models/                     # SQLAlchemy ORM
│   │   ├── utils/                      # zeep_helpers, small helpers only
│   │   └── seeds/                      # Seeder modules (used by scripts)
│   ├── scripts/                        # CLI entry points (seed_db, generate_node_catalog, debug/)
│   ├── tests/                          # unit/, integration/, conftest.py
│   ├── exports/                        # gitignored — CSV/Excel/JSON outputs
│   ├── agenticflow.db                  # gitignored SQLite file
│   ├── alembic/                        # migrations
│   ├── pyproject.toml                  # ruff, black, mypy, pytest config
│   └── requirements.txt                # pinned runtime deps
├── frontend/
│   ├── src/
│   │   ├── api/                        # one file per domain
│   │   ├── components/                 # Canvas/, Chat/, ExecutionLog/, common/
│   │   ├── pages/                      # route-level components
│   │   ├── store/                      # Zustand stores
│   │   ├── styles/                     # Tailwind entry
│   │   └── types/                      # shared TS types
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── eslint.config.js                # flat config
├── docs/
│   ├── SPECIFICATION.md                # what / quality bar
│   ├── ARCHITECTURE.md                 # how, layered
│   ├── IMPLEMENTATION.md               # this file
│   ├── TASKS.md                        # roadmap & retro
│   ├── USAGE.md                        # end-user guide
│   ├── MIGRATIONS.md                   # alembic runbook
│   └── prompt.md                       # onboarding prompt for AI assistants
├── .github/workflows/                  # ci.yml, release.yml
├── .env.example
├── LICENSE
├── README.md
├── CHANGELOG.md
├── SECURITY.md
├── CONTRIBUTING.md
├── llms.txt
├── BASLAT.bat                          # Windows launcher (cosmetic, optional)
└── start_backend.bat / start_frontend.bat
```

**Rules:**
- `app/utils/` is for **small, local** helpers. If a module accumulates mass, promote it to a service.
- Debug / one-off scripts live under `backend/scripts/debug/`, never in repo root.
- `_auto_generated.py` is the only auto-written source file; it has a header marker and is regenerable.

---

## 2. Python Decisions

### 2.1 `pyproject.toml` over `setup.py` / `setup.cfg`
Single source of dep + tool config. Ruff, Black, MyPy, Pytest, Coverage all read from it.

### 2.2 `ruff` + `ruff format` — NOT black + isort + flake8
Ruff covers all three at 10–100x speed. One tool, one config, one CI step.

### 2.3 `mypy --strict` from day one
With strict mode on, `Any` requires justification and every missing return annotation breaks the build. Ticimax SOAP returns are typed as `dict[str, Any]` at the boundary and narrowed as soon as possible.

### 2.4 SQLAlchemy 2.x typed mapped style (not legacy declarative)
`Mapped[int]`, `mapped_column()`, `relationship()` generics — gives mypy full visibility into the ORM.

### 2.5 Alembic over `Base.metadata.create_all`
`init_db()` currently uses `create_all` for developer ergonomics. Production path uses Alembic. When the first schema change lands, `init_db` will be demoted to dev-only and Alembic becomes required for all environments.

### 2.6 `AsyncIOScheduler` on FastAPI's loop
No separate worker process. Jobs dispatch with the app's asyncio loop; DB sessions are per-job (not shared with requests). Trade-off: heavy job counts (10k+) would need a separate worker, but we target single-tenant.

### 2.7 `zeep` factory-namespace fix
Ticimax WSDLs omit namespace declarations that `zeep` expects. Our `fix_factories` pokes the missing namespaces onto the client's factory map. This is documented in `app/utils/zeep_helpers.py` with a link to the `zeep` GitHub issue.

### 2.8 Fernet for `uye_kodu`
Symmetric AES-128-CBC + HMAC. Fast, one-key setup, no public-key infrastructure. The `MASTER_KEY` env must be a 32-byte urlsafe-base64 value. Rotation procedure: `SECURITY.md`.

### 2.9 Anthropic CLI path
`LLM_PROVIDER=anthropic_cli` shells out to the `claude` binary. This exists so users on the Claude Code subscription can run the agent without paying API usage separately. The CLI contract is: JSON-in on stdin, JSON-out on stdout.

### 2.10 Per-step DB commit
Each `ExecutionStep` is committed on status change. This costs a few extra round trips but makes a crashed process recoverable: the history is accurate up to the crash point, and `Execution.status` can be repaired to `ERROR` on next startup (planned in v0.6).

---

## 3. Frontend Decisions

### 3.1 Vite, not Next.js
AgenticFlow is a SPA. No SEO, no server-rendered data, no edge concerns. Vite ships fast HMR and a trivial build.

### 3.2 Zustand, not Redux/Recoil/Jotai
One store per concern (today: `workflowStore`), no provider tree, stable selectors. Redux is overkill for a canvas app.

### 3.3 TanStack Query for all server data
Queries keyed by route + filters. Mutations invalidate their siblings explicitly. No manual `useEffect` fetching.

### 3.4 `@xyflow/react` (React Flow v12)
De-facto standard for node graphs. We use its built-in selection + drag + connection state; only custom node renderers for categories.

### 3.5 Tailwind, not CSS-in-JS
Lower runtime overhead. Utility classes co-locate with markup. Theme extension in `tailwind.config.js`.

### 3.6 No runtime validation library (zod/valibot) in v1.x
Shapes come from the OpenAPI schema indirectly; we hand-type response types in `src/types/`. If drift becomes a pain, `openapi-typescript` + generated types will replace hand-typing.

### 3.7 Strict TS with `"noUncheckedIndexedAccess": true`
Catches the `array[0]` trap. Worth the ergonomics hit.

---

## 4. Node Authoring Conventions

- `type_id`: reverse-DNS-ish, lowercase, dot-separated. `{category}.{domain}.{action}`.
- `display_name`: Turkish, sentence-case, as it will appear in the palette.
- `description`: ≤ 140 chars, explains what & when to use.
- `icon`: a valid `lucide-react` icon name. If none fits, ask; don't invent.
- `color`: use the category color (see `frontend/src/components/Canvas/colors.ts`).
- `config_schema`: exhaustive; every field the UI should show must appear.
- Return shape: prefer `{"result": ...}` at the top level so downstream `{{id.result.*}}` patterns work uniformly.

**Anti-patterns (blocked by review):**
- Returning a non-JSON-serializable object.
- Reading `context.db` for business logic (only engine should touch it).
- Catching all exceptions and returning empty — errors must propagate so the step records them.

---

## 5. Testing Strategy

### 5.1 Layers
- **Unit (`tests/unit/`)** — pure functions, `BaseNode` subclasses with mocked context/services. Fast, < 10 ms each.
- **Integration (`tests/integration/`)** — full executor runs against an in-memory SQLite with fixture workflows; SOAP mocked via a lightweight zeep stub.
- **Contract (`tests/contract/`)** — verifies every node in `NODE_REGISTRY` satisfies the `BaseNode` contract (smoke).

### 5.2 Fixtures
- `db_session` — session-scoped in-memory SQLite.
- `site_factory`, `workflow_factory` — build valid rows with sensible defaults.
- `fake_ticimax` — records calls, returns canned responses.
- `frozen_time` — `freezegun` for scheduler tests.

### 5.3 Coverage rule
- `ruff format`, `ruff check`, `mypy` all pass before any test is considered valid.
- `--cov-fail-under=80` for `app/engine`, `app/services`, `app/nodes/{transform,logic,output,ai,triggers}`.
- Auto-generated Ticimax nodes are excluded from coverage metric but included in the contract test.

---

## 6. CI Design

Single workflow, one job per language, parallel where independent.

```yaml
name: CI
on: [push, pull_request]
jobs:
  backend:
    steps:
      - ruff format --check
      - ruff check
      - mypy
      - pytest --cov --cov-fail-under=80
  frontend:
    steps:
      - prettier --check
      - eslint .
      - tsc --noEmit
      - vitest run --coverage
  audit:
    steps:
      - pip-audit
      - npm audit --omit=dev --audit-level=high
```

A release workflow (`release.yml`) triggered on tag: build frontend, package, create GitHub Release with artifact + changelog excerpt.

---

## 7. What Was Removed / Deferred

- **Multi-tenant tables** (`User`, `Team`, `Membership`): not in v1.x.
- **WebSocket execution progress**: replaced with polling.
- **Queue-based executor (Celery/Arq)**: not needed at current scale.
- **Per-node retry policy**: deferred; for now nodes are the source of their own retry if any.
- **Workflow versioning / snapshots**: deferred; current model overwrites `graph_json`.

Each of these has a slot in `docs/TASKS.md` with a rationale for when it would flip into scope.

---

## 8. Known Sharp Edges (by design)

1. **SQLite writer contention** — APScheduler + HTTP request both writing → occasional `database is locked`. Mitigation: short transactions, WAL mode. Documented in `SECURITY.md` ops section.
2. **Long-running SOAP calls block the event loop** — zeep is sync. Mitigation: `run_in_executor` for known-slow calls, per-site semaphore to avoid concurrent overload of a single Ticimax instance.
3. **Auto-generated node config schemas** are conservative; users may need to override via the raw-JSON config editor.
4. **Agent-generated graphs occasionally reference node types that aren't registered.** The executor rejects them with a helpful error; the chat panel re-prompts the LLM with the real registry.
