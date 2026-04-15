"""Pydantic schemas for Workflow API."""
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class WorkflowBase(BaseModel):
    name: str
    description: str = ""
    site_id: int
    graph_json: dict[str, Any] = Field(default_factory=lambda: {"nodes": [], "edges": []})
    is_active: bool = False


class WorkflowCreate(WorkflowBase):
    pass


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    graph_json: dict[str, Any] | None = None
    is_active: bool | None = None


class WorkflowOut(WorkflowBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class WorkflowRunRequest(BaseModel):
    input_data: dict[str, Any] = Field(default_factory=dict)
