"""Pydantic schemas for the support API."""
from pydantic import BaseModel, Field


class SupportSendRequest(BaseModel):
    ticket_id: int
    uye_id: int
    message: str = Field(..., min_length=1)
    site_id: int = 2
    staff_uye_id: int = 407067  # Fulden Müşteri İlişkileri
