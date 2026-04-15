"""reconcile_interrupted_executions — recover from crash-during-run.

The function must:
- Mark any ``PENDING`` / ``RUNNING`` Execution older than the grace window
  as ``ERROR`` with a clear message.
- Do the same to orphaned ExecutionStep rows.
- Leave ``SUCCESS`` / ``ERROR`` / ``CANCELLED`` / ``SKIPPED`` rows alone.
- Leave very fresh rows (inside the grace window) alone — they belong to
  a newly-dispatched BackgroundTask.
- Be safe to call repeatedly (idempotent).
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.models.execution import Execution, ExecutionStatus, ExecutionStep, TriggerType
from app.startup_recovery import reconcile_interrupted_executions
from app.utils.time import utcnow

pytestmark = pytest.mark.integration


def _make_exec(
    db,
    workflow_id: int,
    *,
    status: ExecutionStatus,
    started_minutes_ago: float = 10.0,
    finished: bool = False,
) -> Execution:
    now = utcnow()
    started_at = now - timedelta(minutes=started_minutes_ago) if started_minutes_ago else None
    execution = Execution(
        workflow_id=workflow_id,
        status=status,
        trigger_type=TriggerType.MANUAL,
        started_at=started_at,
        finished_at=now if finished else None,
        input_data={},
        output_data={},
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


def _make_step(
    db,
    execution_id: int,
    *,
    status: ExecutionStatus,
    started_minutes_ago: float = 10.0,
) -> ExecutionStep:
    step = ExecutionStep(
        execution_id=execution_id,
        node_id="n1",
        node_type="trigger.manual",
        status=status,
        started_at=utcnow() - timedelta(minutes=started_minutes_ago),
        duration_ms=0,
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


def test_running_execution_is_marked_error(db_session, workflow_factory) -> None:
    wf = workflow_factory()
    execution = _make_exec(db_session, wf.id, status=ExecutionStatus.RUNNING)

    result = reconcile_interrupted_executions(db=db_session)

    db_session.refresh(execution)
    assert execution.status == ExecutionStatus.ERROR
    assert "Interrupted" in execution.error
    assert execution.finished_at is not None
    assert result["executions_marked_error"] == 1


def test_pending_execution_with_no_started_at_is_also_recovered(
    db_session, workflow_factory
) -> None:
    wf = workflow_factory()
    execution = _make_exec(
        db_session,
        wf.id,
        status=ExecutionStatus.PENDING,
        started_minutes_ago=0,  # no started_at
    )
    execution.started_at = None
    db_session.commit()

    reconcile_interrupted_executions(db=db_session)

    db_session.refresh(execution)
    assert execution.status == ExecutionStatus.ERROR


def test_success_and_error_rows_untouched(db_session, workflow_factory) -> None:
    wf = workflow_factory()
    success = _make_exec(db_session, wf.id, status=ExecutionStatus.SUCCESS, finished=True)
    done_error = _make_exec(db_session, wf.id, status=ExecutionStatus.ERROR, finished=True)

    reconcile_interrupted_executions(db=db_session)

    db_session.refresh(success)
    db_session.refresh(done_error)
    assert success.status == ExecutionStatus.SUCCESS
    assert done_error.status == ExecutionStatus.ERROR
    assert success.finished_at is not None


def test_fresh_running_within_grace_window_is_untouched(db_session, workflow_factory) -> None:
    wf = workflow_factory()
    # started 1 second ago — inside the 5 s grace window
    execution = Execution(
        workflow_id=wf.id,
        status=ExecutionStatus.RUNNING,
        trigger_type=TriggerType.MANUAL,
        started_at=utcnow() - timedelta(seconds=1),
        input_data={},
        output_data={},
    )
    db_session.add(execution)
    db_session.commit()
    db_session.refresh(execution)

    reconcile_interrupted_executions(db=db_session)

    db_session.refresh(execution)
    assert execution.status == ExecutionStatus.RUNNING  # untouched


def test_steps_are_also_reconciled(db_session, workflow_factory) -> None:
    wf = workflow_factory()
    execution = _make_exec(db_session, wf.id, status=ExecutionStatus.RUNNING)
    running_step = _make_step(db_session, execution.id, status=ExecutionStatus.RUNNING)
    success_step = _make_step(db_session, execution.id, status=ExecutionStatus.SUCCESS)

    result = reconcile_interrupted_executions(db=db_session)

    db_session.refresh(running_step)
    db_session.refresh(success_step)
    assert running_step.status == ExecutionStatus.ERROR
    assert running_step.finished_at is not None
    assert "Interrupted" in running_step.error
    assert success_step.status == ExecutionStatus.SUCCESS  # untouched
    assert result["steps_marked_error"] == 1


def test_is_idempotent(db_session, workflow_factory) -> None:
    wf = workflow_factory()
    _make_exec(db_session, wf.id, status=ExecutionStatus.RUNNING)

    first = reconcile_interrupted_executions(db=db_session)
    second = reconcile_interrupted_executions(db=db_session)

    assert first["executions_marked_error"] == 1
    assert second["executions_marked_error"] == 0  # nothing left to do


def test_clean_state_returns_zero(db_session, workflow_factory) -> None:
    wf = workflow_factory()
    _make_exec(db_session, wf.id, status=ExecutionStatus.SUCCESS, finished=True)

    result = reconcile_interrupted_executions(db=db_session)

    assert result == {"executions_marked_error": 0, "steps_marked_error": 0}
