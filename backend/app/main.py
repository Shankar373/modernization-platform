"""
Enterprise Application Modernization Platform — FastAPI Application Entry Point
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.api import health, ingestion, analysis, migration, reports, capabilities, dependency_analysis, recipes, git_checkpoint
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown."""
    await init_db()
    yield
    # cleanup on shutdown


app = FastAPI(
    title="Enterprise Modernization Platform",
    description=(
        "Language-independent, adapter-based, capability-driven "
        "enterprise application modernization and migration platform."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.get("/", include_in_schema=False)
async def root():
    """Landing page for the API server (the UI lives on the frontend)."""
    return JSONResponse({
        "service": "Enterprise Modernization Platform API",
        "version": "1.0.0",
        "status": "ok",
        "message": "This is the backend API server. Open the web UI at http://localhost:3000 or the API docs at /docs.",
        "docs": "/docs",
    })

# ── Security middleware ────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(ingestion.router, prefix="/api/v1", tags=["Ingestion"])
app.include_router(analysis.router, prefix="/api/v1", tags=["Analysis"])
app.include_router(capabilities.router, prefix="/api/v1", tags=["Capabilities"])
app.include_router(migration.router, prefix="/api/v1", tags=["Migration"])
app.include_router(reports.router, prefix="/api/v1", tags=["Reports"])
app.include_router(dependency_analysis.router, prefix="/api/v1", tags=["Dependency Analysis"])
app.include_router(recipes.router, prefix="/api/v1", tags=["Recipes"])
app.include_router(git_checkpoint.router, prefix="/api/v1", tags=["Git Checkpoint"])
