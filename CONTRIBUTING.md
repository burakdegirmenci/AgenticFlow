# Contributing to AgenticFlow

Thanks for your interest in AgenticFlow! This guide covers local setup, the discipline we follow, and how to get a PR merged.

> Before you start: please read `docs/SPECIFICATION.md` (what this project is and isn't) and `docs/ARCHITECTURE.md` (how it's built). Changes that contradict those documents must update them as part of the PR.

---

## Ground Rules

1. **Spec-first** — non-trivial changes update `docs/SPECIFICATION.md` and/or `docs/ARCHITECTURE.md` before or alongside the code.
2. **Tests come with the code** — no PR merges without tests proving the change.
3. **Lint + typecheck are non-negotiable** — CI must be green; no `# type: ignore`, `// @ts-ignore`, or `eslint-disable` without a comment explaining why.
4. **Single focus per PR** — one feature, one bug, or one refactor. Split large work.
5. **Turkish or English** in docs and code comments; PR titles in English.

---

## Local Setup

### Prerequisites
- Python 3.11+ (3.12 recommended)
- Node.js 20 LTS (22 LTS recommended)
- An Anthropic API key **or** a Google Gemini API key (for the agent; not required for backend unit tests)

### Backend

```bash
cd backend
python -m venv .venv
# Windows:   .venv\Scripts\activate
# Unix:      source .venv/bin/activate

pip install -r requirements.txt
# Once pyproject.toml lands:
# pip install -e ".[dev]"

cp .env.example .env
# Edit .env: set MASTER_KEY (see SECURITY.md for generation)

alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm ci              # use ci, not install, for reproducible builds
npm run dev
```

Open `http://127.0.0.1:5173`.

### Demo Data

```bash
cd backend
python -m scripts.seed_db --site-id 1
```

---

## Everyday Commands

### Backend

| Purpose | Command |
|---|---|
| Run dev server | `uvicorn app.main:app --reload --port 8000` |
| Format code | `ruff format .` |
| Lint | `ruff check .` |
| Fix lint auto | `ruff check . --fix` |
| Type check | `mypy app` |
| Run tests | `pytest` |
| Tests with coverage | `pytest --cov=app --cov-report=term-missing` |
| Regenerate Ticimax node catalog | `python -m scripts.generate_node_catalog` |
| Create migration | `alembic revision --autogenerate -m "your message"` |
| Apply migrations | `alembic upgrade head` |

### Frontend

| Purpose | Command |
|---|---|
| Dev server | `npm run dev` |
| Build | `npm run build` |
| Preview build | `npm run preview` |
| Lint | `npm run lint` |
| Format | `npm run format` |
| Type check | `npm run typecheck` |
| Tests | `npm run test` |
| Test coverage | `npm run test:coverage` |

### Before Committing

```bash
# Backend
cd backend && ruff format . && ruff check . && mypy app && pytest

# Frontend
cd frontend && npm run format && npm run lint && npm run typecheck && npm run test
```

Or just let CI catch it — but local is faster.

---

## Adding a Node

1. Pick a category folder under `backend/app/nodes/` (or create one).
2. Create `<action>.py` with a `BaseNode` subclass:
   ```python
   from app.engine.node_base import BaseNode
   from app.engine.context import ExecutionContext
   from typing import Any

   class MyCoolNode(BaseNode):
       type_id = "category.domain.action"
       category = "transform"
       display_name = "My Cool Node"
       description = "What this does in one sentence."
       icon = "zap"
       color = "#6366f1"
       config_schema = {
           "type": "object",
           "properties": {
               "threshold": {"type": "number", "default": 10}
           },
       }

       async def execute(
           self,
           context: ExecutionContext,
           inputs: dict[str, Any],
           config: dict[str, Any],
       ) -> dict[str, Any]:
           return {"result": ...}
   ```
3. Export it from the category `__init__.py` so `NODE_REGISTRY` picks it up.
4. Add a unit test in `backend/tests/unit/nodes/<category>/test_<action>.py`.
5. Run `pytest backend/tests/unit/nodes/<category>` and `ruff check` locally.
6. If the node renders specially on the canvas, add an entry in `frontend/src/components/Canvas/nodeRenderers.ts`.

See `docs/IMPLEMENTATION.md §4` for naming and anti-pattern rules.

---

## Adding a Ticimax Operation

If it's already in `server.py`:
1. Regenerate: `python -m scripts.generate_node_catalog`.
2. Check the diff in `app/nodes/ticimax/_auto_generated.py`.
3. If the operation deserves special handling (pagination, batching, output shaping), **write a hand-optimized sibling node** and export it instead. The auto-generated one becomes deprecated but stays compatible.

If it's missing from `server.py`:
1. Add it there first (or PR to the upstream SOAP client if appropriate), then regenerate.

---

## Adding an API Endpoint

1. Add request / response Pydantic schemas in `app/schemas/<domain>.py`.
2. Add the route handler in `app/routers/<domain>.py`. Keep it thin — delegate to a service.
3. Add a frontend wrapper in `frontend/src/api/<domain>.ts`.
4. Add tests: happy path + one error path + auth boundary (once auth lands).

---

## Commit & PR Conventions

### Commit Messages
Conventional Commits:
- `feat: add trigger.webhook node`
- `fix: scheduler memory leak on workflow reactivation`
- `refactor: extract zeep factory fix into helper`
- `docs: clarify polling snapshot semantics`
- `test: cover only_new thundering-herd guard`
- `chore: bump fastapi to 0.116`

### PR Description Template
```markdown
## Summary
<1–3 bullets>

## Changes
- <what changed, where>

## Testing
- <how you verified>

## Docs
- [ ] SPECIFICATION.md updated (if needed)
- [ ] ARCHITECTURE.md updated (if needed)
- [ ] CHANGELOG.md entry under [Unreleased]

## Checklist
- [ ] `ruff format` / `ruff check` / `mypy` green
- [ ] `pytest` green; new code has tests
- [ ] Frontend `lint` / `typecheck` / `test` green (if touched)
- [ ] No new `any` / `type: ignore` without justification
```

### PR Size
Target ≤ 400 lines changed. If it's bigger, the reviewer will ask you to split.

---

## Review Process

- One approving review is required; maintainers may self-merge emergency fixes with a post-hoc issue for review.
- CI must be green.
- Docs drift blocks merge.
- The reviewer is allowed — and encouraged — to be picky about naming, contracts, and errors.

## CI & Branch Protection

`main` is protected (active settings via `gh api repos/burakdegirmenci/AgenticFlow/branches/main/protection`):

- ✅ Require a pull request before merging (external contributors)
- ✅ Require approvals: **1**
- ✅ Dismiss stale reviews when new commits are pushed
- ✅ Require review from CODEOWNERS
- ✅ Require status checks to pass:
  - `CI gate` (aggregates backend + frontend + audit)
- ✅ Require branches to be up to date before merging
- ✅ Require conversation resolution before merging
- ⚠️ **Linear history NOT required** — merge commits are allowed so dependabot + AI-agent PRs can merge cleanly without rebase rituals
- ⚠️ **Admins NOT enforced** — the maintainer can direct-push small fixes, hotfixes, or work that does not benefit from a review round-trip; this matches the pragmatic pattern used across the @oxog ecosystem

**CI jobs** (see `.github/workflows/ci.yml`):

| Job | Matrix | Gates |
|---|---|---|
| `backend` | Python 3.11 + 3.12 | `ruff format --check`, `ruff check`, `mypy`, `pytest --cov` |
| `frontend` | Node 20 + 22 | `prettier --check`, `eslint`, `tsc --noEmit`, `vitest run --coverage`, `vite build` |
| `audit` | — | `pip-audit`, `npm audit --audit-level=high` (advisory until Sprint 4) |
| `ci-gate` | — | Aggregate pass/fail — required check for branch protection |

**Dependabot** opens grouped PRs weekly (Mondays 06:00 Europe/Istanbul) for pip, npm, and GitHub Actions. Major version bumps come as separate PRs.

**Releases** (`.github/workflows/release.yml`) trigger on `v*.*.*` tags and:
1. Build backend sdist + wheel.
2. Build frontend production bundle, package as `.tar.gz`.
3. Extract the matching `CHANGELOG.md` section.
4. Create a GitHub Release with notes + artifacts.

Pre-release tags (`-alpha`, `-beta`, `-rc`) are auto-marked as prerelease.

---

## Code of Conduct

Be respectful. Assume good faith. Critique code, not people. Issues get closed for personal attacks without a second warning.

---

## Where to Ask

- **Bugs / feature requests** → GitHub Issues.
- **Security** → See `SECURITY.md`.
- **How-to / general questions** → GitHub Discussions (when enabled).
