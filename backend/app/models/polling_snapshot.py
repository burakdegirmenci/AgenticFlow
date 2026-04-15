"""Polling snapshot - per (workflow, node) memory of previously-seen IDs.

Used by ``transform.only_new`` node to filter a list of items down to the ones
that have not been observed in prior runs of the same workflow/node.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PollingSnapshot(Base):
    __tablename__ = "polling_snapshots"
    __table_args__ = (
        UniqueConstraint("workflow_id", "node_id", name="uq_polling_snapshot_wf_node"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    node_id: Mapped[str] = mapped_column(String(100), nullable=False)
    # Last-seen unique IDs as JSON array of strings.
    last_seen_ids: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
