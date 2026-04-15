"""ApiKeyMiddleware — gate behaviour when `API_KEY` is set.

We build a minimal Starlette app rather than reusing ``app.main.app``
because the production app installs the middleware once at import-time
with the env-configured key. Exercising the logic directly lets us
parameterise the key per test without reloading modules.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.api_key import API_KEY_HEADER, ApiKeyMiddleware

pytestmark = pytest.mark.integration


def _make_app(api_key: str) -> FastAPI:
    app = FastAPI()
    app.add_middleware(ApiKeyMiddleware, api_key=api_key)

    @app.get("/")
    def root() -> dict[str, str]:
        return {"name": "tester"}

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "healthy"}

    @app.get("/metrics")
    def metrics() -> dict[str, str]:
        return {"m": "ok"}

    @app.get("/api/protected")
    def protected() -> dict[str, str]:
        return {"secret": "value"}

    return app


@pytest.fixture
def client_with_key() -> Iterator[TestClient]:
    with TestClient(_make_app("super-secret")) as tc:
        yield tc


@pytest.fixture
def client_no_key() -> Iterator[TestClient]:
    """API_KEY unset → middleware is a pass-through."""
    with TestClient(_make_app("")) as tc:
        yield tc


class TestDisabledByDefault:
    """Empty API_KEY must not touch anything."""

    def test_protected_path_open_when_key_unset(self, client_no_key: TestClient) -> None:
        r = client_no_key.get("/api/protected")
        assert r.status_code == 200
        assert r.json() == {"secret": "value"}

    def test_no_header_no_problem(self, client_no_key: TestClient) -> None:
        assert client_no_key.get("/").status_code == 200


class TestEnabled:
    def test_missing_header_is_401(self, client_with_key: TestClient) -> None:
        r = client_with_key.get("/api/protected")
        assert r.status_code == 401
        body = r.json()
        assert body["detail"] == "Invalid or missing API key"
        assert r.headers.get("WWW-Authenticate", "").startswith("ApiKey")

    def test_wrong_key_is_401(self, client_with_key: TestClient) -> None:
        r = client_with_key.get("/api/protected", headers={API_KEY_HEADER: "not-the-key"})
        assert r.status_code == 401

    def test_correct_key_passes(self, client_with_key: TestClient) -> None:
        r = client_with_key.get("/api/protected", headers={API_KEY_HEADER: "super-secret"})
        assert r.status_code == 200
        assert r.json() == {"secret": "value"}

    @pytest.mark.parametrize("path", ["/", "/health", "/metrics"])
    def test_open_paths_bypass_auth(self, client_with_key: TestClient, path: str) -> None:
        r = client_with_key.get(path)
        assert r.status_code == 200

    def test_options_preflight_is_allowed(self, client_with_key: TestClient) -> None:
        r = client_with_key.options(
            "/api/protected",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        # CORS handling isn't wired in the mini app, but the middleware
        # should hand the request down (FastAPI returns a method-not-allowed).
        assert r.status_code in (200, 405)

    def test_empty_header_is_treated_as_missing(self, client_with_key: TestClient) -> None:
        r = client_with_key.get("/api/protected", headers={API_KEY_HEADER: ""})
        assert r.status_code == 401
