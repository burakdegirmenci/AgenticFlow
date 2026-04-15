"""Startup recovery: reconcile any executions left mid-flight by a crash.

If the process is killed hard (``SIGKILL`` / container OOM / power loss)
while an Execution is ``PENDING`` or ``RUNNING``, its row stays in that
state forever and its ``ExecutionStep`` children may be partially written.
On the next boot this helper:

1. Marks every ``RUNNING`` / ``PENDING`` Execution as ``ERROR`` with a
   clear "interrupted" message and sets ``finished_at = utcnow()``.
2. Marks any ``RUNNING`` / ``PENDING`` ExecutionStep on those executions
   the same way so the history UI doesn't show an orphan "still running"
   row.

This is **safe** because:
- The executor commits per step, so rolled-back steps already reflect
  their last successful state.
- Graceful shutdown (``scheduler_service.shutdown()`` in the lifespan)
  already stops new work; anything still ``RUNNING`` is by definition
  orphaned.
- We only touch executions whose ``started_at`` is older than a small
  grace window (5 s) so a freshly-dispatched background task isn't
  misclassified during the race between ``app.lifespan`` startup and
  ``BackgroundTasks`` firing.

Intended call site: ``app.main.lifespan`` startup, after ``init_db`` and
before the scheduler registers jobs.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.logging_config import get_logger
from app.models.execution import Execution, ExecutionStatus, ExecutionStep
from app.utils.time import utcnow

logger = get_logger("agenticflow.recovery")

_INTERRUPTED_ERROR = "Interrupted by process restart"
_GRACE_WINDOW = timedelta(seconds=5)


def reconcile_interrupted_executions(
    db: Session | None = None,
) -> dict[str, int]:
    """Mark orphaned executions + steps as ERROR. Safe to call multiple times.

    - Production call sites pass nothing; a private ``SessionLocal`` is
      opened and closed here.
    - Tests pass a live ``Session`` bound to the test engine; ownership
      stays with the caller (we commit but don't close).
    """
    owns_session = db is None
    if db is None:
        db = SessionLocal()
    cutoff = utcnow() - _GRACE_WINDOW
    try:
        stale_statuses = (ExecutionStatus.PENDING, ExecutionStatus.RUNNING)

        steps_updated = 0
        stale_steps = (
            db.query(ExecutionStep)
            .filter(ExecutionStep.status.in_(stale_statuses))
            .filter(ExecutionStep.started_at < cutoff)
            .all()
        )
        for step in stale_steps:
            step.status = ExecutionStatus.ERROR
            step.error = _INTERRUPTED_ERROR
            step.finished_at = utcnow()
            steps_updated += 1

        execs_updated = 0
        stale_execs = (
            db.query(Execution)
            .filter(Execution.status.in_(stale_statuses))
            .filter((Execution.started_at.is_(None)) | (Execution.started_at < cutoff))
            .all()
        )
        for execution in stale_execs:
            execution.status = ExecutionStatus.ERROR
            execution.error = _INTERRUPTED_ERROR
            execution.finished_at = utcnow()
            execs_updated += 1

        if execs_updated or steps_updated:
            db.commit()
            logger.warning(
                "startup_recovery_applied",
                extra={
                    "executions_marked_error": execs_updated,
                    "steps_marked_error": steps_updated,
                },
            )
        else:
            # Nothing to write — leave the caller's transaction state alone.
            logger.debug("startup_recovery_clean")

        return {
            "executions_marked_error": execs_updated,
            "steps_marked_error": steps_updated,
        }
    finally:
        if owns_session:
            db.close()
