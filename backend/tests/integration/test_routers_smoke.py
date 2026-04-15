"""FastAPI TestClient smoke tests for the HTTP surface.

Covers the happy-path endpoints every merchant hits in the UI:
- ``/`` and ``/health``
- ``/metrics`` (new in Sprint 5)
- ``/api/nodes`` — catalog used by the palette
- ``/api/sites`` CRUD
- ``/api/workflows`` CRUD + ``/run``
- Request id echo back in the response header

Integration-scoped because we spin up a FastAPI app with the real router
wiring and override only the DB dependency to use the test in-memory
session.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app

pytestmark = pytest.mark.integration


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    """FastAPI TestClient with DB dependency overridden to the test session."""

    def _db_override() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = _db_override
    try:
        with TestClient(app) as tc:
            yield tc
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Infra endpoints
# ---------------------------------------------------------------------------
def test_root_returns_metadata(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "AgenticFlow"
    assert body["status"] == "ok"


def test_health_endpoint(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "healthy"}


def test_ready_endpoint_when_scheduler_started(client: TestClient) -> None:
    """TestClient triggers the lifespan which starts the scheduler."""
    r = client.get("/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["checks"]["db"] == "ok"
    assert body["checks"]["scheduler"] == "ok"


def test_ready_reports_503_when_db_fails(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the DB probe raises, /ready must return 503 and surface the error."""
    from app import main as main_module

    def _broken_session() -> None:
        raise RuntimeError("simulated DB outage")

    monkeypatch.setattr(main_module, "SessionLocal", _broken_session)

    r = client.get("/ready")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "not_ready"
    assert isinstance(body["checks"]["db"], dict)
    assert "simulated DB outage" in body["checks"]["db"]["error"]


def test_metrics_endpoint_returns_prometheus_text(client: TestClient) -> None:
    # Prime a couple counters so the output has content.
    client.get("/")
    client.get("/health")

    r = client.get("/metrics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    text = r.text
    assert "# TYPE agenticflow_requests_total counter" in text
    assert "agenticflow_requests_total" in text


def test_request_id_is_echoed_back(client: TestClient) -> None:
    r = client.get("/health", headers={"X-Request-ID": "trace-abc"})
    assert r.headers.get("X-Request-ID") == "trace-abc"


def test_request_id_generated_when_not_supplied(client: TestClient) -> None:
    r = client.get("/health")
    rid = r.headers.get("X-Request-ID")
    assert rid is not None
    assert len(rid) >= 16


# ---------------------------------------------------------------------------
# /api/nodes — catalog
# ---------------------------------------------------------------------------
def test_nodes_catalog_is_registry_shape(client: TestClient) -> None:
    r = client.get("/api/nodes")
    assert r.status_code == 200
    catalog = r.json()
    assert isinstance(catalog, list)
    assert len(catalog) >= 100
    sample = catalog[0]
    for key in ("type_id", "category", "display_name", "config_schema"):
        assert key in sample


# ---------------------------------------------------------------------------
# /api/sites — CRUD
# ---------------------------------------------------------------------------
def test_sites_crud_happy_path(client: TestClient) -> None:
    # Create
    create = client.post(
        "/api/sites",
        json={"name": "Demo", "domain": "demo.example.com", "uye_kodu": "FON5-XYZ"},
    )
    assert create.status_code == 201, create.text
    site_id = create.json()["id"]

    # List
    listed = client.get("/api/sites").json()
    assert any(s["id"] == site_id for s in listed)

    # Update
    upd = client.patch(f"/api/sites/{site_id}", json={"name": "Demo Renamed"})
    assert upd.status_code == 200
    assert upd.json()["name"] == "Demo Renamed"

    # Delete
    d = client.delete(f"/api/sites/{site_id}")
    assert d.status_code in (200, 204)
    # Fetching after delete is 404
    assert client.get(f"/api/sites/{site_id}").status_code == 404


# ---------------------------------------------------------------------------
# /api/workflows — CRUD
# ---------------------------------------------------------------------------
def test_workflow_create_requires_existing_site(client: TestClient) -> None:
    r = client.post(
        "/api/workflows",
        json={"name": "w1", "site_id": 9999, "graph_json": {"nodes": [], "edges": []}},
    )
    assert r.status_code in (400, 404)


def test_workflow_crud_happy_path(client: TestClient) -> None:
    site = client.post(
        "/api/sites",
        json={"name": "S", "domain": "s.example.com", "uye_kodu": "FON5-S"},
    ).json()

    wf = client.post(
        "/api/workflows",
        json={
            "name": "First",
            "site_id": site["id"],
            "graph_json": {"nodes": [], "edges": []},
        },
    )
    assert wf.status_code == 201, wf.text
    wf_id = wf.json()["id"]

    # Get back
    got = client.get(f"/api/workflows/{wf_id}")
    assert got.status_code == 200
    assert got.json()["name"] == "First"

    # List — filter by site
    listed = client.get(f"/api/workflows?site_id={site['id']}").json()
    assert any(w["id"] == wf_id for w in listed)

    # Patch
    upd = client.patch(f"/api/workflows/{wf_id}", json={"name": "Renamed"})
    assert upd.status_code == 200
    assert upd.json()["name"] == "Renamed"

    # Delete
    d = client.delete(f"/api/workflows/{wf_id}")
    assert d.status_code in (200, 204)


def test_get_missing_workflow_returns_404(client: TestClient) -> None:
    r = client.get("/api/workflows/9999")
    assert r.status_code == 404
