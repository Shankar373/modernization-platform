"""
Dependency Analysis API

Exposes:
  POST /dependency-analysis        — run full pipeline (detect → parse → registry → compare → apply → validate)
  POST /dependency-analysis/plan   — plan-only mode (detect → parse → registry → compare; NO file writes)
  GET  /dependency-analysis/cache-clear — clear cached result for a workspace
"""
from __future__ import annotations

import asyncio
import traceback

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.dependency_analysis.service import DependencyAnalysisService

router = APIRouter()
_service = DependencyAnalysisService()

# In-process cache keyed by (workspace_path, plan_only)
_cache: dict[str, dict] = {}


class DependencyAnalysisRequest(BaseModel):
    workspace_path: str
    project_id: str
    force_refresh: bool = False   # bypass cache, re-query registries
    plan_only: bool = False        # when True: detect + compare, but do NOT write files


@router.post("/dependency-analysis")
async def run_dependency_analysis(request: DependencyAnalysisRequest):
    """
    Run the full dependency analysis pipeline.

    When plan_only=True  → detects + queries registries + compares, but does NOT write any files.
                           Use this for the "Dependency Update Review" step.
    When plan_only=False → full pipeline including applying updates and validation.
                           Use this for the "Apply Dependency Updates" step.
    """
    cache_key = f"{request.workspace_path}::{'plan' if request.plan_only else 'apply'}"

    if not request.force_refresh and cache_key in _cache:
        return {**_cache[cache_key], "cached": True, "project_id": request.project_id}

    try:
        result = await asyncio.to_thread(
            _service.analyze,
            request.workspace_path,
            request.plan_only,
        )

        result_dict = result.model_dump()
        _cache[cache_key] = result_dict

        return {**result_dict, "cached": False, "project_id": request.project_id, "plan_only": request.plan_only}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Dependency analysis failed: {e}\n{traceback.format_exc()[:1200]}",
        )


@router.get("/dependency-analysis/cache-clear")
async def clear_dependency_cache(workspace_path: str):
    """Clear cached analysis results for a workspace."""
    cleared = [k for k in list(_cache.keys()) if k.startswith(workspace_path)]
    for k in cleared:
        del _cache[k]
    return {"cleared": len(cleared) > 0, "workspace_path": workspace_path, "keys_removed": len(cleared)}
