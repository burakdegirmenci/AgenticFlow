"""Time helpers.

Centralises our timezone policy so every DB timestamp, log record, and
trigger payload is produced the same way. `datetime.utcnow()` is deprecated
in Python 3.12; this module is its documented replacement.

Policy: we store **timezone-naive** UTC datetimes in the DB (the SQLAlchemy
columns are `DateTime` without `timezone=True`). That matches the existing
schema and Alembic migrations, so flipping to timezone-aware would be a
breaking change we defer to a future sprint.

Use `utcnow()` everywhere a wall-clock UTC timestamp is needed. Use
`utcnow_iso()` for a JSON-safe ISO-8601 string (no offset suffix).
"""

from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Timezone-naive UTC datetime.

    Drop-in replacement for the deprecated ``datetime.utcnow()``. Produced
    by ``datetime.now(UTC).replace(tzinfo=None)`` so no behaviour change for
    callers that stored the result in naive columns.
    """
    return datetime.now(UTC).replace(tzinfo=None)


def utcnow_iso() -> str:
    """UTC timestamp as an ISO-8601 string without timezone suffix."""
    return utcnow().isoformat()
