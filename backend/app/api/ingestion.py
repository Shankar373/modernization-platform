"""Repository ingestion API — ZIP upload and Git URL."""
import os
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.core.application.ingestion_service import IngestionService, SecurityError

router = APIRouter()
_ingestion = IngestionService()


class GitIngestRequest(BaseModel):
    git_url: str
    branch: Optional[str] = "main"
    project_name: Optional[str] = "unnamed"


class IngestResponse(BaseModel):
    project_id: str
    workspace_path: str
    source_type: str
    message: str


@router.post("/ingest/zip", response_model=IngestResponse)
async def ingest_zip(
    file: UploadFile = File(...),
    project_name: str = Form(default="unnamed"),
):
    """Upload a ZIP archive for analysis."""
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files are supported.")

    content = await file.read()
    try:
        project_id, workspace_path = _ingestion.create_workspace(project_name)
        _ingestion.ingest_zip(content, workspace_path)
        return IngestResponse(
            project_id=project_id,
            workspace_path=workspace_path,
            source_type="zip",
            message="Repository ingested successfully.",
        )
    except SecurityError as e:
        raise HTTPException(status_code=400, detail=f"Security error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")


@router.post("/ingest/git", response_model=IngestResponse)
async def ingest_git(request: GitIngestRequest):
    """Clone a Git repository for analysis."""
    try:
        project_id, workspace_path = _ingestion.create_workspace(request.project_name or "git-project")
        _ingestion.ingest_git(request.git_url, workspace_path, branch=request.branch or "main")
        return IngestResponse(
            project_id=project_id,
            workspace_path=workspace_path,
            source_type="git",
            message="Repository cloned successfully.",
        )
    except SecurityError as e:
        raise HTTPException(status_code=400, detail=f"Security error: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Git ingestion failed: {e}")
