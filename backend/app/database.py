"""SQLAlchemy engine and session management."""
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

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


engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    echo=False,
    json_serializer=_json_serializer,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Session:
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
