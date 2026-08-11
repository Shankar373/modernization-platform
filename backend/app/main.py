"""
Enterprise Application Modernization Platform — FastAPI Application Entry Point
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.config import settings
from app.api import health, ingestion, analysis, migration, reports, capabilities
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
