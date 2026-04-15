"""Workflows CRUD + run."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.engine.executor import WorkflowExecutor
from app.models.execution import ExecutionStatus, TriggerType
from app.models.site import Site
from app.models.workflow import Workflow
from app.schemas.execution import ExecutionOut
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowOut,
    WorkflowRunRequest,
    WorkflowUpdate,
)
from app.services.scheduler_service import scheduler_service

router = APIRouter()


@router.get("", response_model=list[WorkflowOut])
def list_workflows(site_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(Workflow)
    if site_id is not None:
        q = q.filter(Workflow.site_id == site_id)
    return q.order_by(Workflow.id.desc()).all()


@router.get("/scheduler/jobs")
def list_scheduler_jobs():
    """Debug: list currently-scheduled APScheduler jobs."""
    return {"jobs": scheduler_service.list_jobs()}


@router.post("", response_model=WorkflowOut, status_code=status.HTTP_201_CREATED)
def create_workflow(payload: WorkflowCreate, db: Session = Depends(get_db)):
    site = db.query(Site).filter(Site.id == payload.site_id).first()
    if not site:
        raise HTTPException(status_code=400, detail="site_id does not exist")

    wf = Workflow(
        name=payload.name,
        description=payload.description,
        site_id=payload.site_id,
        graph_json=payload.graph_json,
        is_active=payload.is_active,
    )
    db.add(wf)
    db.commit()
    db.refresh(wf)
    return wf


@router.get("/{workflow_id}", response_model=WorkflowOut)
def get_workflow(workflow_id: int, db: Session = Depends(get_db)):
    wf = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf


@router.patch("/{workflow_id}", response_model=WorkflowOut)
def update_workflow(workflow_id: int, payload: WorkflowUpdate, db: Session = Depends(get_db)):
    wf = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    graph_changed = payload.graph_json is not None and payload.graph_json != wf.graph_json
    active_changed = payload.is_active is not None and payload.is_active != wf.is_active

    if payload.name is not None:
        wf.name = payload.name
    if payload.description is not None:
        wf.description = payload.description
    if payload.graph_json is not None:
        wf.graph_json = payload.graph_json
    if payload.is_active is not None:
        wf.is_active = payload.is_active

    db.commit()
    db.refresh(wf)

    # Sync scheduler state when activation or graph changes.
    if active_changed or (graph_changed and wf.is_active):
        if wf.is_active:
            scheduler_service.register_workflow(wf.id)
        else:
            scheduler_service.unregister_workflow(wf.id)

    return wf


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workflow(workflow_id: int, db: Session = Depends(get_db)):
    wf = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    scheduler_service.unregister_workflow(wf.id)
    db.delete(wf)
    db.commit()


async def _run_in_background(execution_id: int) -> None:
    """Spawn a fresh DB session and run the existing execution.

    BackgroundTasks executes after the response is sent, so this function
    must own its session lifecycle.
    """
    db = SessionLocal()
    try:
        await WorkflowExecutor(db).run_existing(execution_id)
    finally:
        db.close()


@router.post("/{workflow_id}/run", response_model=ExecutionOut)
async def run_workflow(
    workflow_id: int,
    background_tasks: BackgroundTasks,
    payload: WorkflowRunRequest | None = None,
    db: Session = Depends(get_db),
):
    """Start a workflow run asynchronously.

    Returns the freshly-created Execution row in PENDING state immediately;
    the actual graph execution happens in a BackgroundTask. Frontend polls
    GET /executions/{id} for live progress.
    """
    wf = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    executor = WorkflowExecutor(db)
    execution = executor.create_execution(
        wf,
        trigger_type=TriggerType.MANUAL,
        trigger_input=(payload.input_data if payload else {}),
        initial_status=ExecutionStatus.PENDING,
    )
    background_tasks.add_task(_run_in_background, execution.id)
    return execution
