"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.routers import sites, workflows, nodes, executions, agent, settings as settings_router, support


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    from app.services.scheduler_service import scheduler_service
    scheduler_service.start()
    scheduler_service.refresh_all()
    yield
    # Shutdown
    scheduler_service.shutdown()


app = FastAPI(
    title="AgenticFlow",
    description="Ticimax workflow automation platform with agentic AI",
    version="0.1.0",
    lifespan=lifespan,
)

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
def root():
    return {"name": "AgenticFlow", "version": "0.1.0", "status": "ok"}


@app.get("/health")
def health():
    return {"status": "healthy"}
