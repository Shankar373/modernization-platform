"""Analysis API — scan repository and return technology profile + capability assessment."""
import asyncio
import traceback

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.orchestration.orchestrator import MigrationOrchestrator

router = APIRouter()
_orchestrator = MigrationOrchestrator()

# ── In-process analysis cache ─────────────────────────────────────────────────
# Key: workspace_path  →  Value: full assessment dict
# Cleared between server restarts; prevents repeated analyze calls from re-scanning.
_analysis_cache: dict[str, dict] = {}


class AnalyzeRequest(BaseModel):
    workspace_path: str
    project_id: str


@router.post("/analyze")
async def analyze_repository(request: AnalyzeRequest):
    """
    Scan the workspace and return:
    - Technology fingerprint (languages, frameworks, build systems, dependencies)
    - Available migration capabilities per language
    - Unsupported languages (returned as NOT_AVAILABLE / ASSESSMENT_ONLY)
    - Target version recommendations

    Optimizations applied:
    - Runs in asyncio.to_thread() so the event loop stays unblocked (fixes WinError 64)
    - Result cached in memory per workspace_path — repeated calls are instant
    """
    try:
        cache_key = request.workspace_path

        # Return cached result if available (avoids re-scanning same workspace)
        if cache_key in _analysis_cache:
            cached = _analysis_cache[cache_key]
            return {
                "project_id": request.project_id,
                "workspace_path": request.workspace_path,
                "cached": True,
                **cached,
            }

        # Run the blocking scan OFF the event loop thread (fixes Windows WinError 64)
        def _do_scan():
            profile = _orchestrator.scan(request.workspace_path)
            return _orchestrator.get_assessment(request.workspace_path, profile)

        assessment = await asyncio.to_thread(_do_scan)

        # Cache for subsequent calls
        _analysis_cache[cache_key] = assessment

        return {
            "project_id": request.project_id,
            "workspace_path": request.workspace_path,
            "cached": False,
            **assessment,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {e}\n{traceback.format_exc()[:1000]}"
        )
