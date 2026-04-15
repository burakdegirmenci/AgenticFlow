# AgenticFlow — AI Assistant / New-Contributor Onboarding Prompt

> Paste this into any capable coding assistant (Claude, Cursor, Copilot) working on AgenticFlow, or read it yourself as a new contributor.

---

You are working on **AgenticFlow**, a self-hosted, single-tenant automation platform for Ticimax e-commerce merchants. Visual node-based workflow builder + agentic AI chat. Written in Python (FastAPI + SQLAlchemy 2.x + SQLite + APScheduler + Zeep) on the backend and React 18 + TypeScript + Vite + React Flow on the frontend. License MIT.

## Rules You Will Follow

1. **Read `docs/SPECIFICATION.md` first.** It is authoritative. If your proposed change contradicts it, either update the spec (with a justification in the PR description) or abandon the change.
2. **Read `docs/ARCHITECTURE.md` next.** Your change must fit the layered model (routers → services → engine → nodes → models). Do not put business logic in routers.
3. **Read `docs/IMPLEMENTATION.md` for context** on why specific choices were made. If you are tempted to change one of those choices, bring receipts (benchmarks, bug reports, citations).
4. **Run the full quality gate locally before claiming done:**
   - Backend: `ruff format .` · `ruff check .` · `mypy app` · `pytest`
   - Frontend: `npm run format` · `npm run lint` · `npm run typecheck` · `npm run test`
5. **Every code change ships with tests.** Non-negotiable.
6. **Never weaken a type.** `Any`, `// @ts-ignore`, `# type: ignore` require a comment justifying the exception.
7. **Never commit secrets.** `.env`, `agenticflow.db`, `exports/*`, `_ui_test_screens/` are gitignored for a reason.
8. **Node contract:**
   - Subclass `BaseNode` in `backend/app/engine/node_base.py`.
   - `type_id` = `{category}.{domain}.{action}` (reverse-DNS style, lowercase).
   - Provide exhaustive `config_schema` (JSON Schema subset).
   - Return a JSON-serializable dict, ideally `{"result": ...}` at the top level so downstream `{{id.result.*}}` templates work.
   - Register via the category's `__init__.py` so `NODE_REGISTRY` picks it up.
   - One unit test minimum.
9. **Ticimax SOAP** goes through `ticimax_service`. Do not call `zeep.Client` directly from a node.
10. **Scheduler** changes go through `SchedulerService`. Do not start a second scheduler.
11. **LLM calls** go through `app/services/llm/`. Respect the `anthropic_api` / `anthropic_cli` / `google_genai` provider switch.
12. **Frontend state:** server data lives in **TanStack Query**; canvas draft state lives in **Zustand**; URL state lives in query params. No duplication.
13. **Updating docs is part of the task**, not an afterthought.

## Non-Goals (Will Reject PRs That Try These)

- Multi-tenant mode, user accounts, RBAC.
- Celery / RQ / Arq / Redis queues.
- CSS-in-JS (styled-components, emotion, etc.).
- Runtime schema libraries on the frontend (zod/valibot) in v1.x.
- Workflow versioning/snapshots in v1.0 — it's on the v1.1 roadmap.
- Custom YAML/Python DSL for graphs.

## Common Tasks

### Add a node
```
1. Create backend/app/nodes/<category>/<action>.py with a BaseNode subclass.
2. Export from category __init__.py.
3. Unit test in backend/tests/unit/nodes/<category>/test_<action>.py.
4. Run ruff, mypy, pytest.
5. If it needs special canvas rendering, update frontend/src/components/Canvas/nodeRenderers.ts.
```

### Add a Ticimax operation
```
1. If present in server.py: python -m scripts.generate_node_catalog, then diff.
2. If it needs special handling (pagination, batching), write a hand-optimized sibling node — do not edit _auto_generated.py directly.
3. If missing from server.py, add it there first.
```

### Add an API endpoint
```
1. Pydantic schemas in backend/app/schemas/<domain>.py.
2. Thin route handler in backend/app/routers/<domain>.py; delegate to a service.
3. Frontend wrapper in frontend/src/api/<domain>.ts.
4. Tests: happy path + one error path.
```

## Where to Start as a New Contributor

1. `docs/SPECIFICATION.md` — understand scope.
2. `docs/ARCHITECTURE.md` — understand layers.
3. `backend/app/engine/executor.py` — understand how workflows run.
4. `backend/app/engine/node_base.py` — understand the node contract.
5. `backend/app/nodes/transform/only_new.py` — read a non-trivial node end-to-end.
6. `frontend/src/pages/WorkflowEditor.tsx` — understand the canvas.
7. Pick an item from `docs/TASKS.md` under the **Now** section.

## Style Notes

- Turkish or English in comments and docs; PR titles in English.
- Prefer narrow, named return types over tuples.
- Prefer composition over inheritance (except `BaseNode` — that's the one inheritance axis).
- If a function needs a docstring to be understandable, write the docstring; if it needs it to be refactorable, refactor.
- Keep the executor simple. Its job is orchestration, not cleverness.

---

When in doubt: read the spec, write the test, ship the smallest correct change.
