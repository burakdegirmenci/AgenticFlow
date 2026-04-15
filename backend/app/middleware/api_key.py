"""Optional `X-Api-Key` authentication.

Threat model (v1.1+): AgenticFlow is single-tenant. If the operator exposes
the UI / API beyond localhost without a reverse-proxy auth layer in front
(Traefik basic-auth, OAuth2 proxy, VPN, SSH tunnel, ...), a shared API key
is the minimum viable gate.

Policy:
- When ``API_KEY`` env is empty, this middleware is a no-op. That preserves
  the current behaviour for local-dev / private-network deployments.
- When ``API_KEY`` is set, every request must carry ``X-Api-Key: <value>``
  OR be on the allowlist of open paths (``/health``, ``/metrics``, ``/``,
  OpenAPI docs). Mismatches return 401 JSON.
- OPTIONS / CORS preflights are allowed through.

The header name is chosen over `Authorization: Bearer …` to keep it
disjoint from any future token-based scheme, and to signal "shared secret,
not a user identity".
"""

from __future__ import annotations

import hmac
from collections.abc import Awaitable, Callable
from typing import Final

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.logging_config import get_logger

logger = get_logger("agenticflow.auth")

API_KEY_HEADER: Final = "X-Api-Key"

# Paths that work without a key even when API_KEY is set. Infra + docs only.
_OPEN_PATHS: Final[frozenset[str]] = frozenset(
    {
        "/",
        "/health",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
    }
)


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Enforce ``X-Api-Key`` when a key is configured.

    Instantiated with the expected key string. Passing an empty string
    disables the middleware (the dispatcher becomes a pass-through).
    """

    def __init__(self, app: ASGIApp, api_key: str) -> None:
        super().__init__(app)
        self._api_key = api_key
        self._enabled = bool(api_key)
        if self._enabled:
            logger.info("api_key_middleware_enabled")
        else:
            logger.debug("api_key_middleware_disabled")

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not self._enabled:
            return await call_next(request)

        # Preflights and open paths always allowed.
        if request.method == "OPTIONS" or request.url.path in _OPEN_PATHS:
            return await call_next(request)

        supplied = request.headers.get(API_KEY_HEADER) or ""
        # Constant-time comparison to avoid timing oracles on the key.
        if not supplied or not hmac.compare_digest(supplied, self._api_key):
            logger.warning(
                "api_key_rejected",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "has_header": bool(supplied),
                },
            )
            return JSONResponse(
                {"detail": "Invalid or missing API key"},
                status_code=401,
                headers={"WWW-Authenticate": f'ApiKey header="{API_KEY_HEADER}"'},
            )

        return await call_next(request)
