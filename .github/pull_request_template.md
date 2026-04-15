<!--
Thanks for contributing to AgenticFlow! Before opening this PR, please read:
- CONTRIBUTING.md  — PR rules and local commands
- docs/SPECIFICATION.md — what the project is and isn't
- docs/prompt.md — discipline summary for contributors (human or AI)
-->

## Summary

<!-- 1–3 sentences: what this PR changes and why. -->

## Changes

- <!-- list of notable changes by file or area -->

## Testing

<!-- How did you verify this works? -->
- [ ] `cd backend && ruff format . && ruff check . && mypy app && pytest`
- [ ] `cd frontend && npm run ci`
- [ ] Manual smoke test (describe what you clicked through)

## Documentation

- [ ] `docs/SPECIFICATION.md` updated, or no spec-visible change
- [ ] `docs/ARCHITECTURE.md` updated, or no architectural change
- [ ] `CHANGELOG.md` entry under `## [Unreleased]`
- [ ] `docs/TASKS.md` status updated, if this closes a tracked task

## Checklist

- [ ] PR targets `main` (or a long-lived feature branch).
- [ ] Change is focused — one feature / bug / refactor. (Split if not.)
- [ ] No new `# type: ignore`, `// @ts-ignore`, `eslint-disable`, or `any` without a comment justifying it.
- [ ] No secrets, tokens, `uye_kodu`, or customer data in diffs / tests / screenshots.
- [ ] If a new environment variable was introduced, it is in `.env.example` and documented in `SPECIFICATION.md §4.4`.
- [ ] If a new node was added, it has a unit test and follows `docs/IMPLEMENTATION.md §4`.

## Related Issues / Discussions

<!-- e.g. "Closes #42", "Refs #17". -->
