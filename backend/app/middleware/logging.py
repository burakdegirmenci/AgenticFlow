"""HTTP request logging middleware.

Emits one JSON log line per HTTP request with method, path, status, duration,
and a request_id header echoed back to the client for correlation. Keeps
execution logs (executor-side) and HTTP logs (router-side) joinable.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.logging_config import get_logger
from app.metrics import REQUESTS_TOTAL

logger = get_logger("agenticflow.http")

_REQUEST_ID_HEADER = "X-Request-ID"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request and expose a request_id for correlation."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get(_REQUEST_ID_HEADER) or uuid.uuid4().hex
        t0 = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            logger.exception(
                "http_request_failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                },
            )
            REQUESTS_TOTAL.increment(status="5xx", method=request.method)
            raise

        duration_ms = int((time.perf_counter() - t0) * 1000)
        response.headers[_REQUEST_ID_HEADER] = request_id

        status_class = f"{response.status_code // 100}xx"
        REQUESTS_TOTAL.increment(status=status_class, method=request.method)

        # Stay quiet for /health + /metrics so polling doesn't drown real traffic.
        if request.url.path in ("/health", "/metrics"):
            return response

        logger.info(
            "http_request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
