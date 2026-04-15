"""Pydantic schemas for Site API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SiteBase(BaseModel):
    name: str
    domain: str


class SiteCreate(SiteBase):
    uye_kodu: str


class SiteUpdate(BaseModel):
    name: str | None = None
    domain: str | None = None
    uye_kodu: str | None = None


class SiteOut(SiteBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class SiteConnectionTest(BaseModel):
    status: str
    services: dict | None = None
    error: str | None = None
