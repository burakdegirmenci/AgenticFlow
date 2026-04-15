# AgenticFlow — Deployment Guide

This doc covers **self-hosted, single-tenant** deployment. The project does
not ship a SaaS mode (see `docs/SPECIFICATION.md §2.2`).

Target environments:
- A single Linux host (VPS / Hetzner / DigitalOcean droplet) with Docker.
- A private network where **you** own the reverse proxy / TLS termination.
- Low-concurrency: one user or a small ops team.

If any of those don't match your setup, the defaults may need tightening.

---

## 1. Quickstart (Docker Compose)

On a fresh host:

```bash
git clone https://github.com/burakdegirmenci/AgenticFlow.git
cd AgenticFlow

# .env — see section 3 for every variable
cp backend/.env.example .env
${EDITOR:-nano} .env        # fill MASTER_KEY + one LLM provider key

# Build + launch
docker compose up -d --build

# Verify
curl -sf http://localhost:8080/health      # frontend → backend passthrough
curl -sf http://localhost:8080/metrics | head
```

Visit `http://localhost:8080` in a browser.

Stop / restart:

```bash
docker compose stop          # pause — state preserved
docker compose start         # resume
docker compose down          # containers removed, volumes survive
```

### What the Compose Stack Runs

| Service | Image | Ports | Volumes |
|---|---|---|---|
| `backend` | `python:3.12-slim` + uvicorn | internal only | `./data` (SQLite), `./logs` (JSON logs), `./backend/exports` |
| `frontend` | `nginx:1.27-alpine` + Vite bundle | `8080 → 80` | — |

The backend is **not** exposed on the host by default — the frontend nginx
proxies `/api`, `/metrics`, `/health`. Uncomment the `ports:` block under
`backend:` in `docker-compose.yml` if you need to reach it directly for
debugging.

---

## 2. Image Builds

```bash
# Rebuild after dep changes:
docker compose build --pull

# Tag for a release:
docker compose build
docker tag agenticflow-backend:local  ghcr.io/you/agenticflow-backend:v0.6.0
docker tag agenticflow-frontend:local ghcr.io/you/agenticflow-frontend:v0.6.0
docker push ghcr.io/you/agenticflow-backend:v0.6.0
docker push ghcr.io/you/agenticflow-frontend:v0.6.0
```

Image highlights:
- Backend is **multistage** (builder venv → slim runtime), non-root user,
  `tini` as PID 1, `HEALTHCHECK` against `/health`.
- Frontend bundle is produced with `npm ci && npm run build` in a Node
  stage, then served by `nginx:alpine`. SPA fallback to `/index.html`,
  hashed `/assets/*` cached for a year.

---

## 3. Environment Variables

Required to boot:

| Var | What | Source |
|---|---|---|
| `MASTER_KEY` | Fernet key for `uye_kodu` encryption at rest. | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `ANTHROPIC_API_KEY` **or** `GOOGLE_API_KEY` | At least one — agent chat and in-workflow AI nodes need a provider. | Anthropic console / Google AI Studio |

Optional:

| Var | Default | When to set |
|---|---|---|
| `LLM_PROVIDER` | `anthropic_api` | `anthropic_cli` for Claude Code subscription; `google_genai` for Gemini. |
| `CLAUDE_MODEL_AGENT`, `CLAUDE_MODEL_NODE`, `GEMINI_MODEL_AGENT`, `GEMINI_MODEL_NODE` | sane defaults | Pin to a specific model version for reproducibility. |
| `CLAUDE_CLI_PATH` | `claude` | Absolute path when `claude` is not on `$PATH`. |
| `DATABASE_URL` | `sqlite:////data/agenticflow.db` | Override for a mounted disk or Postgres (experimental). |
| `LOG_LEVEL` | `INFO` | `DEBUG` to see per-step traces. |
| `LOG_DIR` | `logs` → `/var/log/agenticflow` in Docker | Empty string disables file logging (stdout only). |
| `LOG_FILE` | `agenticflow.log` | Renaming is rarely useful. |
| `CORS_ORIGINS` | compose default | Comma-separated list of allowed web origins. **Tighten this for public deployments.** |
| `HOST`, `PORT` | `0.0.0.0`, `8000` | Bind address inside the container. |
| `SENTRY_DSN` | empty | Turn on Sentry error tracking. Install the extra: `pip install agenticflow-backend[sentry]`. |
| `API_KEY` | empty | Optional `X-Api-Key` gate. See §5. |

---

## 4. Reverse Proxy + TLS

The included nginx serves the SPA + proxies `/api`; it does **not**
terminate TLS or add external auth. Put your own reverse proxy in front.

### 4.1 Example: Traefik

```yaml
# docker-compose.override.yml
services:
  frontend:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.agenticflow.rule=Host(`flow.example.com`)"
      - "traefik.http.routers.agenticflow.entrypoints=websecure"
      - "traefik.http.routers.agenticflow.tls.certresolver=letsencrypt"
      - "traefik.http.services.agenticflow.loadbalancer.server.port=80"
    ports: []        # drop the host 8080 binding
```

Remember to set `CORS_ORIGINS=https://flow.example.com` on the backend.

### 4.2 Example: Caddy

```caddy
flow.example.com {
    reverse_proxy localhost:8080
}
```

### 4.3 Example: Nginx (system)

```nginx
server {
    server_name flow.example.com;
    listen 443 ssl http2;

    ssl_certificate     /etc/letsencrypt/live/flow.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/flow.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        # Let agent streams flow.
        proxy_buffering off;
        proxy_read_timeout 120s;
    }
}
```

---

## 5. Authentication

AgenticFlow is single-tenant with **no built-in user system**. Protect it at
the network boundary. In order of strength:

1. **VPN / SSH tunnel / Tailscale.** Don't expose the UI publicly.
2. **Reverse-proxy auth** (Traefik basic-auth middleware, Caddy
   `basic_auth`, Cloudflare Access, OAuth2 proxy). Preferred for teams.
3. **Built-in `X-Api-Key`.** Set `API_KEY` in `.env` and have clients send
   `X-Api-Key: <value>`. Constant-time comparison. Open paths are
   `/`, `/health`, `/metrics`, `/docs`, `/redoc`, `/openapi.json`. This is a
   shared secret — it does **not** identify individual users.

Do **not** publish the UI on the open internet without at least one of
the above active.

---

## 6. Database Operations

### 6.1 First Boot

On the first `docker compose up`, the backend's lifespan calls
`init_db()` which creates the schema from SQLAlchemy models. Once live,
switch to Alembic for every subsequent schema change — see
`docs/MIGRATIONS.md`.

To force Alembic from the start (recommended for new deployments):

```bash
# Don't let init_db run; run Alembic first:
docker compose run --rm backend alembic upgrade head
docker compose up -d
```

### 6.2 Backups

SQLite + WAL: the DB is one file, plus `-wal` and `-shm` sidecars while
the app is running. Safe backup:

```bash
# Option A — quick cold backup (app must be stopped):
docker compose stop backend
tar czf backup_$(date +%F).tgz data/agenticflow.db data/agenticflow.db-wal data/agenticflow.db-shm
docker compose start backend

# Option B — hot backup via sqlite .backup (app stays up):
docker compose exec -T backend \
  sqlite3 /data/agenticflow.db ".backup /data/backup_$(date +%F).sqlite"
cp data/backup_*.sqlite /your/archive/
```

Keep **weekly** full backups + the **last 7 daily** hot backups on a
different volume. Test restore at least once per year.

### 6.3 Migrations

See `docs/MIGRATIONS.md` for the full runbook. Short version:

```bash
docker compose stop backend
# Backup first!
cp data/agenticflow.db data/agenticflow.db.$(date +%F)
docker compose run --rm backend alembic upgrade head
docker compose start backend
```

---

## 7. Logs & Metrics

### 7.1 Structured Logs

- JSON records on stdout (captured by Docker: `docker compose logs -f backend`).
- Rotating file in `./logs/agenticflow.log` (10 MB × 5 backups by default).
- Secret-redaction filter strips values whose key name matches
  `api_key`, `secret`, `password`, `token`, `uye_kodu`, `master_key`,
  `sentry_dsn` before the record leaves the process.

### 7.2 Metrics

`GET /metrics` returns Prometheus text. Sample scrape config:

```yaml
scrape_configs:
  - job_name: agenticflow
    scrape_interval: 30s
    static_configs:
      - targets: ["flow.example.com"]
    metrics_path: /metrics
    scheme: https
```

Counters exposed:

- `agenticflow_requests_total{method, status}`
- `agenticflow_executions_total{trigger, status}`
- `agenticflow_execution_steps_total{node_type, status}`

### 7.3 Sentry (Optional)

```bash
pip install agenticflow-backend[sentry]
# or in Docker: add `sentry-sdk[fastapi]` to requirements.txt
```

Set `SENTRY_DSN=<your dsn>`. Traces are off by default; only errors are
captured. PII is disabled.

---

## 8. Upgrading

```bash
cd AgenticFlow
git fetch --tags
git checkout v0.6.1            # or the tag you want
docker compose build --pull
# Migrate BEFORE starting new code:
docker compose stop backend
cp data/agenticflow.db data/agenticflow.db.pre-v0.6.1
docker compose run --rm backend alembic upgrade head
docker compose up -d
docker compose logs -f backend   # watch for startup errors
```

Every release's breaking changes are called out in `CHANGELOG.md`.

---

## 9. Operational Sharp Edges

| Thing | Mitigation |
|---|---|
| `database is locked` | WAL is enabled (`PRAGMA journal_mode = WAL`); `busy_timeout = 5000`. If you still see it, reduce concurrent executions or migrate to Postgres. |
| Disk full from `exports/` | Not auto-cleaned. Add a cron in section 10. |
| Disk full from `logs/` | Rotated by stdlib (10 MB × 5). Bump retention in `app/logging_config.py` if you want more. |
| SOAP timeout avalanche | Ticimax occasionally stalls — zeep has a 30 s default. See `docs/IMPLEMENTATION.md §8` for the per-site concurrency roadmap. |
| Shutdown during execution | Scheduler drains on `SIGTERM`; in-flight executions are marked `ERROR` with the interruption reason on next startup (planned Sprint 7). |

---

## 10. Housekeeping Cron Suggestions

Drop these in the host crontab:

```cron
# Daily hot backup, keep 7 days.
0 3 * * * cd /opt/AgenticFlow && docker compose exec -T backend sqlite3 /data/agenticflow.db ".backup /data/backup_$(date +\%F).sqlite" && find data/backup_*.sqlite -mtime +7 -delete

# Weekly export cleanup (exports older than 30 days).
0 4 * * 0 find /opt/AgenticFlow/backend/exports -type f -mtime +30 -delete
```

---

## 11. Checklist Before Opening Publicly

- [ ] TLS in front (Traefik / Caddy / nginx / Cloudflare).
- [ ] `CORS_ORIGINS` restricted to your public host.
- [ ] `API_KEY` set **or** reverse-proxy auth in place.
- [ ] `MASTER_KEY` backed up separately from the DB (rotate procedure:
  `SECURITY.md §Rotation`).
- [ ] `SENTRY_DSN` set (optional but worth it).
- [ ] Prometheus (or equivalent) scraping `/metrics`.
- [ ] Backup cron verified — do a test restore to scratch disk.
- [ ] `docker compose logs -f backend` monitored or shipped somewhere
  greppable.
