# Legacy Scripts

These files were the original way features were verified before a proper
pytest suite existed (see `docs/TASKS.md` Sprint 1). They are kept here for
reference while their coverage is migrated into `backend/tests/`.

## Migration Status

- [ ] `smoke_test_set_siparis_durum.py` → `tests/integration/test_set_siparis_durum_batch.py`
- [ ] `smoke_test_update_oa1.py` → `tests/integration/test_update_ozel_alan_1_batch.py`
- [ ] `ui_test_dry_run.py` → `tests/integration/test_workflow_dry_run.py`
- [ ] `ui_test_oa1.py` → folded into the OA1 batch test above
- [ ] `ui_test_schedule.py` → `tests/integration/test_scheduler_registration.py`
- [ ] `ui_test_wf9_dryrun.py` → folded into the dry-run test
- [ ] `test_support_*.py` (7 files) → `tests/integration/test_support_workflow.py` (one consolidated suite)

## Rules

- **Do not add new scripts here.** Write a real pytest test.
- When you migrate a script, update the checkbox above and delete the script in the same PR.
- Once all boxes are checked, delete this directory and its entry from `docs/TASKS.md`.
