"""Shared pytest fixtures.

Scope rationale:
- ``db_engine``: session-scoped, one in-memory SQLite per test session.
- ``db_session``: function-scoped, rolls back after each test for isolation.
- ``site`` / ``workflow``: function-scoped factories that write to ``db_session``.
- ``fake_ticimax``: function-scoped so tests don't leak call history.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

import pytest
from cryptography.fernet import Fernet

# Ensure MASTER_KEY is present before any app import (config.py validates it
# lazily, but CryptoService refuses to operate without it). Use a fresh test
# key so we never risk touching real data.
os.environ.setdefault("MASTER_KEY", Fernet.generate_key().decode())
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-anthropic")
os.environ.setdefault("GOOGLE_API_KEY", "test-key-google")

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.engine.context import ExecutionContext
from app.models.site import Site
from app.models.workflow import Workflow
from app.services.crypto_service import CryptoService


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    """One in-memory SQLite engine per test session.

    We use ``StaticPool``-style sharing indirectly by reusing a single engine;
    each test gets its own session and explicit transaction via ``db_session``.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    """Function-scoped session that rolls back on teardown for isolation."""
    connection = db_engine.connect()
    transaction = connection.begin()
    TestingSession = sessionmaker(bind=connection, expire_on_commit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------
@pytest.fixture
def site_factory(db_session: Session):
    """Callable that builds a persisted Site with sensible defaults."""
    counter = {"n": 0}

    def _make(
        *,
        name: str | None = None,
        domain: str | None = None,
        uye_kodu: str = "TEST-UYE-KODU",
    ) -> Site:
        counter["n"] += 1
        site = Site(
            name=name or f"Test Site {counter['n']}",
            domain=domain or f"test{counter['n']}.example.com",
            uye_kodu_encrypted=CryptoService.encrypt(uye_kodu),
        )
        db_session.add(site)
        db_session.commit()
        db_session.refresh(site)
        return site

    return _make


@pytest.fixture
def site(site_factory) -> Site:
    """A single persisted Site for the common case."""
    return site_factory()


@pytest.fixture
def workflow_factory(db_session: Session, site: Site):
    """Callable that builds a persisted Workflow bound to the default site."""
    counter = {"n": 0}

    def _make(
        *,
        name: str | None = None,
        graph: dict[str, Any] | None = None,
        is_active: bool = False,
        site_id: int | None = None,
    ) -> Workflow:
        counter["n"] += 1
        wf = Workflow(
            name=name or f"Test Workflow {counter['n']}",
            description="",
            site_id=site_id if site_id is not None else site.id,
            graph_json=graph or {"nodes": [], "edges": []},
            is_active=is_active,
        )
        db_session.add(wf)
        db_session.commit()
        db_session.refresh(wf)
        return wf

    return _make


@pytest.fixture
def execution_context(db_session: Session, site: Site, workflow_factory) -> ExecutionContext:
    """A minimal ExecutionContext suitable for unit-testing nodes in isolation.

    We create a real ``Workflow`` row so tests that write rows referencing
    ``workflow_id`` (e.g. ``polling_snapshots``) don't trip the FK constraint
    enforced by ``PRAGMA foreign_keys = ON``.
    """
    wf = workflow_factory()
    return ExecutionContext(
        execution_id=1,
        workflow_id=wf.id,
        site=site,
        db=db_session,
        trigger_input={},
    )


# ---------------------------------------------------------------------------
# Fake Ticimax client
# ---------------------------------------------------------------------------
class FakeTicimaxClient:
    """Recording stub that mimics the subset of ``TicimaxClient`` nodes use.

    Tests can program responses with ``set_response("method_name", value)``.
    Every call is recorded on ``calls`` as a ``(method, args, kwargs)`` tuple.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self._responses: dict[str, Any] = {}

    def set_response(self, method: str, value: Any) -> None:
        self._responses[method] = value

    def __getattr__(self, name: str) -> Any:
        # Any attribute access returns a callable that records the call and
        # returns the programmed response (or an empty dict).
        def _call(*args: Any, **kwargs: Any) -> Any:
            self.calls.append((name, args, kwargs))
            return self._responses.get(name, {})

        return _call


@pytest.fixture
def fake_ticimax() -> FakeTicimaxClient:
    """A fresh FakeTicimaxClient per test."""
    return FakeTicimaxClient()


@pytest.fixture
def patch_ticimax_service(monkeypatch: pytest.MonkeyPatch, fake_ticimax: FakeTicimaxClient):
    """Replace ``TicimaxService.get_client`` so nodes get the fake client.

    Usage:
        def test_something(patch_ticimax_service, fake_ticimax, ...):
            fake_ticimax.set_response("urun_select", {"UrunList": [...]})
            ...
    """
    from app.services import ticimax_service as ts_module

    monkeypatch.setattr(
        ts_module.TicimaxService,
        "get_client",
        classmethod(lambda cls, site: fake_ticimax),
    )
    monkeypatch.setattr(
        ts_module.TicimaxService,
        "get_by_id",
        classmethod(lambda cls, db, site_id: fake_ticimax),
    )
    return fake_ticimax
