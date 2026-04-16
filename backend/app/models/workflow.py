"""Workflow model - graph JSON stored as dict."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.time import utcnow


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False)
    # React Flow compatible: {"nodes": [...], "edges": [...]}
    graph_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # Optional JSON Schema describing parameters the user must fill in
    # before each run (e.g. file upload, date range, customer ID).
    # When null/empty, "Run" executes immediately (current behaviour).
    input_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    site: Mapped["Site"] = relationship("Site", lazy="joined")  # type: ignore[name-defined]
    executions: Mapped[list["Execution"]] = relationship(  # type: ignore[name-defined]
        "Execution", back_populates="workflow", cascade="all, delete-orphan"
    )
