# Security Policy

## Supported Versions

AgenticFlow is pre-1.0. Only the latest `0.x` minor release receives security fixes.

| Version | Supported |
|---|---|
| 0.5.x (latest) | ✅ |
| < 0.5 | ❌ |

Once 1.0 ships, the current major + previous major will be supported.

---

## Reporting a Vulnerability

**Do not open a public issue for a suspected vulnerability.**

Email the maintainer with:
- A description of the vulnerability and its impact.
- Steps to reproduce (ideally with a minimal workflow graph or HTTP request).
- The affected version / commit.

You will receive an acknowledgement within 72 hours. If the issue is confirmed, a fix will be scheduled and a patched release tagged before public disclosure.

Please allow up to **14 days** for a fix before disclosing publicly.

---

## Threat Model

### Trusted
- The operator running the AgenticFlow process.
- The host filesystem (`agenticflow.db`, `exports/`, `.env`).
- The reverse proxy / network boundary the operator places in front of the UI.

### Untrusted
- The public internet.
- Any user reaching the HTTP API without passing through the operator's access layer.
- Third-party LLM providers (prompts may include business data; operator accepts this).
- Ticimax SOAP responses (treated as data; zeep-level XML parsing is the boundary).

### Explicitly NOT protected (v1.x)
- **Multi-user authentication / RBAC.** AgenticFlow is single-tenant. The operator is expected to protect the UI and API with a reverse proxy, VPN, or SSH tunnel. v1.1 will introduce an optional `X-Api-Key` header middleware.
- **Resource exhaustion attacks** from authenticated users (which is no-one other than the operator in v1.x).

---

## Credential Handling

### Ticimax `uye_kodu`
- Stored in `sites.uye_kodu_encrypted` as a Fernet token.
- Decrypted in-memory only when a `TicimaxClient` is instantiated.
- **Never** appears in execution step data, logs, or API responses.

### LLM API Keys (`ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`)
- Loaded from `.env`; `.env` is gitignored.
- Never leave the server process.
- Never logged.

### `MASTER_KEY`
- 32-byte urlsafe-base64 Fernet key.
- Required; app refuses to start without it.
- Generation:
  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```

### Rotation Procedure (`MASTER_KEY`)
1. Stop the app.
2. Decrypt all `sites.uye_kodu_encrypted` values with the current `MASTER_KEY` (script: `backend/scripts/rotate_master_key.py`, planned v0.6).
3. Generate a new `MASTER_KEY`.
4. Re-encrypt all values with the new key.
5. Update `.env`.
6. Start the app and verify site connections via the UI.

Until the rotation script ships, rotation requires running Python with both old and new keys available and updating the DB manually.

---

## Secrets in Logs

A dedicated log filter redacts any string matching:
- `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `MASTER_KEY` env values at startup.
- Keys present in `sites.uye_kodu_encrypted` (decrypted form).

If structured logging (planned v0.6) surfaces a new code path that could leak secrets, a test must assert that a known secret value is absent from the log output.

---

## Dependencies

- `pip-audit` and `npm audit --audit-level=high` run in CI.
- A failing audit blocks the release workflow.
- Dependabot (weekly) opens PRs for patch + minor updates automatically.

### Pinning Strategy
- `requirements.txt`: versions pinned with `==` for reproducibility (lockfile role).
- `pyproject.toml`: ranges with caret / minor-range for flexibility.
- `package-lock.json`: committed; `npm ci` used in CI.

---

## Known Operational Risks

| Risk | Mitigation |
|---|---|
| SQLite `database is locked` under scheduler + HTTP contention | Short transactions; enable WAL mode; single worker assumption |
| Long-running zeep SOAP call blocks event loop | `run_in_executor` for known-slow operations; per-site concurrency semaphore |
| Malicious LLM-generated graph references harmful node operations | The executor only dispatches registered node types; destructive Ticimax operations (delete, bulk update) are hand-written nodes that validate config before calling SOAP |
| Agent prompt injection via Ticimax data | User is shown the proposed graph before it runs; no auto-execute |
| Export directory fills disk | `exports/` is gitignored; operator is responsible for rotation. A cleanup job is planned for v0.6. |
| `.env` committed by accident | `.gitignore` entry + CI check planned in Sprint 1 |

---

## Checklist for Pull Requests Touching Security Paths

- [ ] New env variable? Document in `.env.example` and `SPECIFICATION.md §4.4`.
- [ ] New log site? Ensure redaction filter covers it.
- [ ] New external call? Timeout + retry policy spelled out.
- [ ] New DB write? Short-lived transaction; no uncommitted state held across `await`.
- [ ] New node? Validates all config fields before any side effect.
