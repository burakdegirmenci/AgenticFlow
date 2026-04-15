"""SQLAlchemy engine and session management."""

import json
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()


def _json_serializer(value: object) -> str:
    """JSON serializer used for SQLAlchemy JSON columns.

    Falls back to ``str()`` for any value that the default encoder cannot
    handle (e.g. ``datetime``, Decimal, custom objects). Without this,
    Ticimax SOAP responses containing ``datetime`` fields cause the
    execution_steps INSERT/UPDATE to fail with TypeError.
    """
    return json.dumps(value, default=str, ensure_ascii=False)


_IS_SQLITE = settings.DATABASE_URL.startswith("sqlite")

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if _IS_SQLITE else {},
    echo=False,
    json_serializer=_json_serializer,
)


if _IS_SQLITE:

    @event.listens_for(Engine, "connect")
    def _sqlite_pragmas(dbapi_connection: object, _connection_record: object) -> None:
        """Apply SQLite pragmas on every new connection.

        - ``journal_mode = WAL`` lets a writer coexist with concurrent readers;
          that's the single biggest lever against ``database is locked`` when
          the scheduler, an HTTP request, and a background execution race to
          write (see docs/ARCHITECTURE.md §11 sharp-edge 1).
        - ``synchronous = NORMAL`` trades a tiny durability window on power
          loss for a ~2x write throughput — acceptable for single-tenant
          self-hosted usage with a filesystem backup plan.
        - ``foreign_keys = ON`` matches the model-level FKs we've declared.
        - ``busy_timeout`` blocks a writer rather than raising immediately
          when another transaction holds the write lock.
        """
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        try:
            cursor.execute("PRAGMA journal_mode = WAL")
            cursor.execute("PRAGMA synchronous = NORMAL")
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute("PRAGMA busy_timeout = 5000")
        finally:
            cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables if they don't exist (MVP fallback, use Alembic for prod)."""
    # Import all models so they register with Base.metadata
    from app.models import (  # noqa: F401
        app_setting,
        chat,
        execution,
        polling_snapshot,
        site,
        workflow,
    )

    Base.metadata.create_all(bind=engine)
