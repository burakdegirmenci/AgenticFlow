# AgenticFlow — Database Migrations

Authoritative runbook for Alembic migrations. Read this before changing any
column on a model.

---

## 1. Policy

- **Alembic is the canonical schema path in production.** Every schema change
  ships as a revision file under `backend/alembic/versions/`.
- `app.database.init_db()` (`Base.metadata.create_all`) is a **dev-only
  convenience**. It is called from the FastAPI lifespan to get you a working
  DB on a fresh clone without running `alembic upgrade head` manually.
- CI does not run migrations today; a smoke test that applies the head
  revision to an empty SQLite will land in a future sprint.

---

## 2. Tooling

Alembic ships as a backend runtime dep (see `backend/pyproject.toml`). With
the dev venv activated, every command below is run from `backend/`:

```bash
cd backend
source venv/Scripts/activate    # Windows-friendly path
```

The `DATABASE_URL` used by every Alembic command is **whatever
`app.config.get_settings()` resolves it to** — normally from `.env`. Never
edit `alembic.ini`'s `sqlalchemy.url` by hand; `env.py` overrides it.

---

## 3. Everyday Commands

| Purpose | Command |
|---|---|
| Create a new revision from model diff | `alembic revision --autogenerate -m "add users.email index"` |
| Apply all pending revisions | `alembic upgrade head` |
| Roll back the last revision | `alembic downgrade -1` |
| Show current head | `alembic current` |
| Show full history | `alembic history` |
| Stamp an existing DB at `head` without running it | `alembic stamp head` |

---

## 4. Writing a New Revision

1. **Edit the SQLAlchemy model** (`backend/app/models/*.py`). Add the column,
   index, relationship, or constraint.
2. **Generate the revision**:
   ```bash
   alembic revision --autogenerate -m "describe the change"
   ```
3. **Read the generated file carefully.** Autogenerate is a best-effort diff:
   - Type changes (`String(100)` → `String(200)`) are detected.
   - Server defaults and triggers often need manual touch-up.
   - Renames are **not** detected — autogenerate writes them as drop+add.
     Rewrite as an `op.alter_column(..., new_column_name=...)` if you want
     to preserve the data.
4. **Run the forward migration** locally against a copy of your DB:
   ```bash
   cp agenticflow.db agenticflow.db.pre-revision
   alembic upgrade head
   ```
5. **Verify the reverse**. Every revision must be reversible:
   ```bash
   alembic downgrade -1
   alembic upgrade head
   ```
   If `downgrade` can't be written safely (e.g. data already transformed),
   document it in the revision's docstring.
6. **Commit** both the model change and the revision file in the same PR.

---

## 5. SQLite-Specific Rules

AgenticFlow's default DB is SQLite and it has sharp edges compared to
Postgres/MySQL:

- **`ALTER TABLE` is limited.** Alembic's `render_as_batch=True` (set in
  `env.py`) copies the table to a temp, re-creates it with the new shape,
  and renames — supporting adds, drops, and type changes. Beware: if the
  batch recreate fails halfway, you're left with a partial temp table. Back
  up the DB before long migrations.
- **No `SET NOT NULL` on existing columns without a backfill.** Provide a
  server default or fill rows in a separate data migration step before
  tightening the column.
- **Foreign keys are only enforced when `PRAGMA foreign_keys = ON`.**
  `app/database.py` sets this on every connection; migrations inherit it.
- **WAL + migration** — long schema changes can block concurrent readers
  briefly. For zero-downtime, stop the backend before `alembic upgrade`.

---

## 6. Deployment Flow

In Docker / production:

```bash
# 1. Stop the app (graceful — scheduler drains, see ARCHITECTURE.md §4).
docker compose stop backend

# 2. Back up the SQLite file.
cp data/agenticflow.db data/agenticflow.db.$(date +%Y%m%d_%H%M%S)

# 3. Apply migrations (run Alembic INSIDE the container so the Python env
#    and DATABASE_URL match the app's).
docker compose run --rm backend alembic upgrade head

# 4. Start the app.
docker compose start backend
```

A convenience wrapper script (`scripts/deploy_migrate.sh`) will land in a
future sprint.

---

## 7. Disaster Recovery

If you need to roll back schema + data to a pre-release state:

```bash
# 1. Stop the app.
docker compose stop backend

# 2. Restore the backup.
cp data/agenticflow.db.<timestamp> data/agenticflow.db

# 3. Stamp Alembic at the revision that file was produced with — if you
#    remember it; otherwise:
docker compose run --rm backend alembic history | less     # find the SHA
docker compose run --rm backend alembic stamp <revision>

# 4. Start the app.
docker compose start backend
```

**Important:** `alembic downgrade` is *code*-driven; if the backup is older
than the revision in code, downgrading will try to undo revisions that
never ran on that DB. `alembic stamp` is the safe way to re-sync state.

---

## 8. Common Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| `Target database is not up to date` on upgrade | DB has revisions the code doesn't know about (e.g. from a rolled-back branch) | `alembic stamp head` then re-run `alembic upgrade head` after pulling latest code |
| `Can't locate revision identified by '…'` | Revision file deleted or missing | Restore the file; don't delete revisions once merged |
| Autogenerate diff is enormous on first run after checking out a branch | Models diverged from live DB | Work against a fresh copy of the DB or stamp current DB at a known revision |
| `database is locked` during `upgrade` | Scheduler / request still holding a write transaction | Stop the backend first — `alembic upgrade` is not meant to run while the app is live |

---

## 9. History

| Revision | Summary | Notes |
|---|---|---|
| `cd868abd5d6d` | Baseline schema (Sprint 6) | Creates `sites`, `workflows`, `executions`, `execution_steps`, `polling_snapshots`, `chat_sessions`, `chat_messages`, `app_settings`. Autogenerated from `app.models.*` at the Sprint 6 cut. |
