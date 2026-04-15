"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from app.config import get_settings
from app.database import init_db
from app.logging_config import get_logger, setup_logging
from app.metrics import render_prometheus
from app.middleware.logging import RequestLoggingMiddleware
from app.routers import (
    agent,
    executions,
    nodes,
    settings as settings_router,
    sites,
    support,
    workflows,
)

settings = get_settings()

# Logging must be configured BEFORE any logger is created in imported modules
# that end up firing at import time.
setup_logging(
    level=settings.LOG_LEVEL,
    log_dir=settings.LOG_DIR or None,
    log_file=settings.LOG_FILE,
)

logger = get_logger("agenticflow.main")


def _init_sentry_if_configured() -> None:
    """Wire Sentry only when SENTRY_DSN is set and the SDK is installed.

    The SDK lives in the optional ``sentry`` extra. We never crash the app if
    it's missing — we just skip initialisation with a warning.
    """
    if not settings.SENTRY_DSN:
        return
    try:
        # SDK lives in the optional `sentry` extra — mypy ignore configured
        # globally via [[tool.mypy.overrides]] in pyproject.toml.
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
    except ImportError:
        logger.warning(
            "sentry_sdk_not_installed",
            extra={"hint": "pip install agenticflow-backend[sentry]"},
        )
        return
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[FastApiIntegration()],
        traces_sample_rate=0.0,
        send_default_pii=False,
    )
    logger.info("sentry_initialised")


_init_sentry_if_configured()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    from app.services.scheduler_service import scheduler_service

    scheduler_service.start()
    scheduler_service.refresh_all()
    logger.info("app_started", extra={"version": app.version})
    yield
    # Shutdown
    scheduler_service.shutdown()
    logger.info("app_stopped")


app = FastAPI(
    title="AgenticFlow",
    description="Ticimax workflow automation platform with agentic AI",
    version="0.5.0",
    lifespan=lifespan,
)

# Order matters: request logging runs inside CORS (so we still log OPTIONS).
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(sites.router, prefix="/api/sites", tags=["sites"])
app.include_router(workflows.router, prefix="/api/workflows", tags=["workflows"])
app.include_router(nodes.router, prefix="/api/nodes", tags=["nodes"])
app.include_router(executions.router, prefix="/api/executions", tags=["executions"])
app.include_router(agent.router, prefix="/api/agent", tags=["agent"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["settings"])
app.include_router(support.router, prefix="/api/support", tags=["support"])


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "AgenticFlow", "version": app.version, "status": "ok"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> str:
    """Prometheus-text exposition of in-process counters.

    Safe to scrape without authentication on a private network; behind a
    reverse proxy, restrict by path if exposing publicly.
    """
    return render_prometheus()
