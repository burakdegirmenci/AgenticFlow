# Security Incident — 2026-04-15 — Leaked Ticimax Üye Kodu

> Internal incident record. Kept under `docs/` intentionally so the
> remediation narrative stays with the repo, and future contributors can
> see what was done + why.

## TL;DR

A live Ticimax `uye_kodu` (32-character customer token) plus an
identifying customer brand name leaked into the repo's docs and UI
placeholders. The repo was briefly (~30 min) public. Source was redacted,
git history was scrubbed, the repo was deleted + recreated so the old
orphan blobs were purged from GitHub's storage, and the affected token
was rotated in Ticimax.

## Timeline (UTC+3)

| Time | Event |
|---|---|
| 2026-04-14 | Token + brand first committed to `docs/USAGE.md`, `README.md`, `frontend/src/pages/Sites.tsx`, `backend/app/seeds/support_workflow.py` during early development |
| 2026-04-15 ~11:20 | Initial v0.5.0 tag + first public release created |
| 2026-04-15 ~11:37 | Repo visibility flipped `private → public`, topics added |
| 2026-04-15 ~12:05 | First deploy smoke test found 2 unrelated bugs; fixed + pushed |
| 2026-04-15 ~12:20 | Security triage: `git grep` found the real token + brand name in 4 files |
| 2026-04-15 ~12:22 | Repo flipped back `public → private` |
| 2026-04-15 ~12:25 | Source redacted in all 4 files (generic example data) |
| 2026-04-15 ~12:30 | `git filter-repo` scrubbed token + brand from the full history |
| 2026-04-15 ~12:35 | Original `v0.5.0` tag + GitHub Release deleted; force-push of clean history |
| 2026-04-15 ~12:38 | Re-cut `v0.5.0` pointing to clean commit; release workflow produced new assets |
| 2026-04-15 ~12:45 | Orphan Dependabot PR refs (`refs/pull/*/head`) still referenced tainted commits — resolution: delete + recreate the repo |
| 2026-04-15 ~12:50 | Repo deleted + recreated cleanly. Branch protection + topics + discussions restored. |
| 2026-04-15 ~12:55 | Ticimax üye kodu **rotated** in the customer's Ticimax admin panel (done by maintainer, out of band) |

Total public exposure window: **~30 minutes.**

## Root Cause

No process existed to sanitize example data before the repo went public.
`docs/USAGE.md` was written early as an internal how-to and used real
credentials because it was "just for me". That file was never flagged
before visibility was flipped.

Contributing factors:
- No secret-scanning pre-commit hook.
- No staged `public-ready` checklist between "private dev" and
  "flip to public".
- Seed data (`support_workflow.py`) embedded brand-specific system prompt
  because it was a faithful port of the original worker.

## Impact Assessment

| Asset | Exposure |
|---|---|
| `uye_kodu` (32 chars) | Publicly readable for ~30 minutes on a brand-new repo with zero stars / watchers at time of leak |
| Customer brand name | Same window |
| Internal business policies (carrier, refund SLA) | Same window |
| Any DB / other secrets | **None** — `.env`, `agenticflow.db`, LLM API keys never committed (verified via `git log --name-only` sweep) |

**Realistic risk of external exploitation:** low-to-moderate. Window is
short and search engines don't instantly crawl private→public flips,
but we cannot prove zero exposure. Token rotation converts any leaked
copy into a useless string.

## Remediation Actions (all completed)

1. **Source sanitation** — 4 files redacted to generic example data
   (`Demo Store`, `demo.example.com`, placeholder token pattern).
2. **History scrub** — `git filter-repo --replace-text` across every
   commit, mapping the leaked token + brand → safe placeholders.
3. **Commit-message scrub** — the redaction commit's own message was
   amended so the token prefix + brand name don't appear anywhere in
   the new history.
4. **Force-push** after temporarily relaxing branch-protection
   (`allow_force_pushes=true`); re-locked immediately after.
5. **Tag + Release recut** — deleted both and recreated from the
   clean commit.
6. **Repo delete + recreate** — because `refs/pull/*/head` on
   Dependabot PRs still pointed at tainted commits that `git filter-repo`
   cannot unlink; deletion was the only way to guarantee those orphan
   blobs stop being reachable on GitHub.
7. **Token rotation** — the affected `uye_kodu` was revoked in the
   Ticimax admin panel and a new one issued to the customer.
8. **Local backup** containing the tainted history was deleted.

## Preventive Measures (landing in Sprint 8)

- [ ] **Pre-commit hook for secrets** — `gitleaks` or `trufflehog` on
      `pre-commit`; blocks any match in staged files.
- [ ] **Pre-publish checklist** appended to `CONTRIBUTING.md` §"Before
      flipping visibility".
- [ ] **Placeholder policy** — all `docs/`, README, and UI placeholders
      must use `Demo Store` / `demo.example.com` / `FONx...` patterns.
      Linter rule to enforce.
- [ ] **CI scan** — gitleaks run on every push + PR; fails the build
      on any high-entropy match.
- [ ] **Audit seed data** — every `app/seeds/*.py` treated as
      "public-facing"; brand names banned.

## Lessons

- "Private for now" is a shipping antipattern. Write every file as if
  it will be public tomorrow.
- **Token rotation** is the only defense that survives caching,
  crawlers, and third-party archives. Source cleanup is necessary but
  not sufficient.
- Force-push + tag recreate is not enough on GitHub; Dependabot and
  other bot-generated refs keep old commits reachable. Delete-and-
  recreate is the clean path for a brand-new repo that hasn't accrued
  community value yet.
- The first public-flip is a high-risk moment. A 5-minute checklist
  would have caught this.

## Sign-off

- Owner: Burak Değirmenci
- Date of closure: 2026-04-15
- Residual risk: token rotated; assumed low.
