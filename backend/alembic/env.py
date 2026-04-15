"""Alembic environment — wires migrations to the live app engine + metadata.

Project policy:
- Alembic is the canonical schema bootstrap path in production.
  ``app.database.init_db`` (``create_all``) remains a dev convenience only.
- The ``DATABASE_URL`` in ``.env`` (via ``pydantic-settings``) is the single
  source of truth — we intentionally ignore ``sqlalchemy.url`` in
  ``alembic.ini`` so there is no drift between runtime and migration URLs.
- SQLite uses ``batch`` mode so ALTER TABLE operations work.
"""

from __future__ import annotations

# Make the `app` package importable when alembic is invoked from backend/.
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

_here = Path(__file__).resolve().parent
_backend_root = _here.parent
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

# Import ONLY after sys.path is prepared.
from app.config import get_settings  # noqa: E402
from app.database import Base  # noqa: E402

# Register every model module so its tables are attached to Base.metadata.
from app.models import (  # noqa: E402, F401
    app_setting,
    chat,
    execution,
    polling_snapshot,
    site,
    workflow,
)

# Alembic Config object — reads values from alembic.ini.
config = context.config

# Override `sqlalchemy.url` with the live setting so there's one source of truth.
config.set_main_option("sqlalchemy.url", get_settings().DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# MetaData object for 'autogenerate'.
target_metadata = Base.metadata


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — emits SQL to stdout."""
    url = config.get_main_option("sqlalchemy.url") or ""
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=_is_sqlite(url),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode — opens a real DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section) or {},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=_is_sqlite(str(connection.engine.url)),
            # Compare column types + server defaults so alters are detected.
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
