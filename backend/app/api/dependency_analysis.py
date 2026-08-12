"""
Dependency Analysis API

Exposes two endpoints:
  POST /dependency-analysis        — run full pipeline on a workspace
  GET  /dependency-analysis/status — return last cached result for a workspace

Reuses the same router / caching pattern as analysis.py.
"""
from __future__ import annotations

import asyncio
import traceback

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.dependency_analysis.service import DependencyAnalysisService

router = APIRouter()
_service = DependencyAnalysisService()

# In-process cache: workspace_path → DependencyAnalysisResult dict
# Cleared on server restart; avoids redundant registry calls for same workspace.
_cache: dict[str, dict] = {}


class DependencyAnalysisRequest(BaseModel):
    workspace_path: str
    project_id: str
    force_refresh: bool = False  # set True to bypass cache and re-query registries


@router.post("/dependency-analysis")
async def run_dependency_analysis(request: DependencyAnalysisRequest):
    """
    Run the full dependency analysis pipeline:

    1. Detect dependency files (requirements.txt, pom.xml, package.json, …)
    2. Parse dependencies from each file
    3. Query package registries for the latest stable version of each dependency
    4. Compare current vs. latest (respect explicit version constraints)
    5. Generate update plan
    6. Apply updates to non-lockfiles
    7. Validate the updated files
    8. Return structured DependencyAnalysisResult

    Registry lookups run in parallel (ThreadPoolExecutor).
    Lockfiles are never modified.
    Network failures result in LOOKUP_FAILED status per dependency,
    not a hard pipeline failure.
    """
    cache_key = request.workspace_path

    if not request.force_refresh and cache_key in _cache:
        return {**_cache[cache_key], "cached": True, "project_id": request.project_id}

    try:
        # Registry lookups are blocking I/O — run off the event loop thread
        result = await asyncio.to_thread(
            _service.analyze,
            request.workspace_path,
        )

        result_dict = result.model_dump()
        _cache[cache_key] = result_dict

        return {**result_dict, "cached": False, "project_id": request.project_id}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Dependency analysis failed: {e}\n{traceback.format_exc()[:1200]}",
        )


@router.get("/dependency-analysis/cache-clear")
async def clear_dependency_cache(workspace_path: str):
    """Clear the cached analysis result for a workspace (forces fresh registry lookup)."""
    removed = _cache.pop(workspace_path, None)
    return {"cleared": removed is not None, "workspace_path": workspace_path}
