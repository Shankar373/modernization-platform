"""Analysis API — scan repository and return technology profile + capability assessment."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.orchestration.orchestrator import MigrationOrchestrator

router = APIRouter()
_orchestrator = MigrationOrchestrator()


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
    """
    try:
        profile = _orchestrator.scan(request.workspace_path)
        assessment = _orchestrator.get_assessment(request.workspace_path, profile)
        return {
            "project_id": request.project_id,
            "workspace_path": request.workspace_path,
            **assessment,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")
