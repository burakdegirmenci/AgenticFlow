"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import text

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.logging_config import get_logger, setup_logging
from app.metrics import render_prometheus
from app.middleware.api_key import ApiKeyMiddleware
from app.middleware.logging import RequestLoggingMiddleware
from app.routers import (
    agent,
    executions,
    nodes,
    settings as settings_router,
    sites,
    support,
    uploads,
    workflows,
)
from app.startup_recovery import reconcile_interrupted_executions

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
    # Reconcile any Execution / ExecutionStep left mid-flight by a previous
    # hard crash (SIGKILL, OOM, power loss). Safe to call on every boot.
    reconcile_interrupted_executions()

    from app.services.scheduler_service import scheduler_service

    scheduler_service.start()
    scheduler_service.refresh_all()
    logger.info("app_started", extra={"version": app.version})
    yield
    # Shutdown — AsyncIOScheduler.shutdown(wait=False) is already called
    # inside SchedulerService.shutdown(). Any in-flight executions that
    # the scheduler dispatched as BackgroundTasks are allowed to finish
    # on their own event loop. Anything that doesn't finish before the
    # worker is killed is picked up by reconcile_interrupted_executions
    # on the next boot.
    scheduler_service.shutdown()
    logger.info("app_stopped")


app = FastAPI(
    title="AgenticFlow",
    description="Ticimax workflow automation platform with agentic AI",
    version="0.5.0",
    lifespan=lifespan,
)

# Middleware order (Starlette executes add_middleware in REVERSE — the last
# added runs first on the way in). We want:
#   request → [CORS] → [auth] → [logging] → [route]
# so CORS preflights are answered first, then auth gates the API surface,
# then each admitted request is logged with its final identity.
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(ApiKeyMiddleware, api_key=settings.API_KEY)
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
app.include_router(uploads.router, prefix="/api/uploads", tags=["uploads"])


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "AgenticFlow", "version": app.version, "status": "ok"}


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe. Returns 200 while the process is running.

    Used by container runtimes (`HEALTHCHECK`) and reverse-proxy
    upstream-health pollers. Does NOT verify dependencies; see `/ready`
    for that. A failing `/health` means the container should be
    restarted.
    """
    return {"status": "healthy"}


@app.get("/ready")
def ready() -> JSONResponse:
    """Readiness probe. Returns 200 only when dependencies respond.

    - **DB**: runs ``SELECT 1`` on a fresh session. If the disk is gone,
      the file is locked, or the engine is misconfigured, this is where
      you find out.
    - **Scheduler**: must have been started by the lifespan hook.

    On partial failure the response is 503 with a per-check breakdown so
    orchestrators (k8s, docker-compose healthcheck, Traefik) can hold
    traffic off until the app is truly ready.
    """
    checks: dict[str, object] = {}
    is_ready = True

    # --- DB -----------------------------------------------------------
    db = None
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as e:  # noqa: BLE001
        checks["db"] = {"status": "error", "error": str(e)[:200]}
        is_ready = False
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:  # noqa: BLE001
                pass

    # --- Scheduler ----------------------------------------------------
    from app.services.scheduler_service import scheduler_service

    scheduler_started = scheduler_service.is_started()
    checks["scheduler"] = "ok" if scheduler_started else "not_started"
    if not scheduler_started:
        is_ready = False

    body = {"status": "ready" if is_ready else "not_ready", "checks": checks}
    code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(body, status_code=code)


@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> str:
    """Prometheus-text exposition of in-process counters.

    Safe to scrape without authentication on a private network; behind a
    reverse proxy, restrict by path if exposing publicly.
    """
    return render_prometheus()
