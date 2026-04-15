"""Pydantic schemas for Execution API."""
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict

from app.models.execution import ExecutionStatus, TriggerType


class ExecutionStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    node_id: str
    node_type: str
    status: ExecutionStatus
    started_at: datetime
    finished_at: datetime | None
    input_data: dict[str, Any]
    output_data: dict[str, Any]
    error: str
    duration_ms: int


class ExecutionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workflow_id: int
    status: ExecutionStatus
    trigger_type: TriggerType
    started_at: datetime | None
    finished_at: datetime | None
    input_data: dict[str, Any]
    output_data: dict[str, Any]
    error: str
    created_at: datetime


class ExecutionDetailOut(ExecutionOut):
    steps: list[ExecutionStepOut]
