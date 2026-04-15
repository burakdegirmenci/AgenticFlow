"""Execution history API."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.execution import Execution, ExecutionStatus, TriggerType
from app.models.workflow import Workflow
from app.schemas.execution import ExecutionDetailOut, ExecutionOut

router = APIRouter()


@router.get("", response_model=list[ExecutionOut])
def list_executions(
    workflow_id: int | None = None,
    status: ExecutionStatus | None = None,
    trigger_type: TriggerType | None = None,
    since: datetime | None = None,
    search: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List executions with optional filters.

    Filters:
        workflow_id: only executions belonging to this workflow
        status: SUCCESS | ERROR | RUNNING | PENDING | CANCELLED | SKIPPED
        trigger_type: MANUAL | SCHEDULE | POLLING | AGENT
        since: ISO datetime, returns executions started at/after this instant
        search: matches error text or workflow name (case-insensitive)
    """
    q = db.query(Execution)
    if workflow_id is not None:
        q = q.filter(Execution.workflow_id == workflow_id)
    if status is not None:
        q = q.filter(Execution.status == status)
    if trigger_type is not None:
        q = q.filter(Execution.trigger_type == trigger_type)
    if since is not None:
        q = q.filter(Execution.started_at >= since)
    if search:
        pattern = f"%{search}%"
        q = q.outerjoin(Workflow, Execution.workflow_id == Workflow.id).filter(
            or_(Execution.error.ilike(pattern), Workflow.name.ilike(pattern))
        )
    limit = max(1, min(limit, 500))
    return q.order_by(Execution.id.desc()).limit(limit).all()


@router.get("/{execution_id}", response_model=ExecutionDetailOut)
def get_execution(execution_id: int, db: Session = Depends(get_db)):
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return execution
