"""Pydantic schemas for the agent chat API."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SessionCreateRequest(BaseModel):
    title: str | None = None
    workflow_id: int | None = None


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    workflow_id: int | None
    created_at: datetime


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    session_id: int
    role: str
    content: str
    tool_use: dict[str, Any] | None
    created_at: datetime


class ChatRequest(BaseModel):
    session_id: int | None = None
    message: str = Field(..., min_length=1)
    workflow_id: int | None = None
    provider: str | None = None  # override global default
    model: str | None = None


class WorkflowProposal(BaseModel):
    name: str
    description: str = ""
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


class ProviderInfo(BaseModel):
    name: str
    display_name: str
    supports_tools: bool
    supports_streaming: bool
    available: bool
    reason: str
