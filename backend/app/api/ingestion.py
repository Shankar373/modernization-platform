from pathlib import Path
from typing import Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.application.ingestion_service import IngestionService, SecurityError
from app.db.session import get_db
from app.db.crud import CRUDRepository

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
    db: AsyncSession = Depends(get_db),
):
    """Upload a ZIP archive for analysis."""
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files are supported.")

    content = await file.read()
    try:
        # Use uploaded file basename if project_name is default "unnamed"
        clean_filename = file.filename[:-4] if file.filename.endswith(".zip") else file.filename
        effective_name = project_name if project_name and project_name != "unnamed" else clean_filename

        project_id, workspace_path = _ingestion.create_workspace(effective_name)
        _ingestion.ingest_zip(content, workspace_path)

        # Save project name for download naming
        try:
            (Path(workspace_path) / ".project_name").write_text(effective_name, encoding="utf-8")
        except Exception:
            pass

        # Save project to DB
        await CRUDRepository.create_project(
            db=db,
            project_id=project_id,
            name=effective_name,
            source_type="zip",
            source_path=file.filename or "uploaded.zip",
            workspace_path=workspace_path,
        )

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
async def ingest_git(request: GitIngestRequest, db: AsyncSession = Depends(get_db)):
    """Clone a Git repository for analysis."""
    try:
        # Extract repo name from Git URL (e.g. https://github.com/user/my-repo.git -> my-repo)
        git_url_name = request.git_url.rstrip("/").split("/")[-1].removesuffix(".git")
        effective_name = request.project_name if request.project_name and request.project_name != "unnamed" else git_url_name

        project_id, workspace_path = _ingestion.create_workspace(effective_name)
        _ingestion.ingest_git(request.git_url, workspace_path, branch=request.branch or "main")

        # Save project name for download naming
        try:
            (Path(workspace_path) / ".project_name").write_text(effective_name, encoding="utf-8")
        except Exception:
            pass

        # Save project to DB
        await CRUDRepository.create_project(
            db=db,
            project_id=project_id,
            name=effective_name,
            source_type="git",
            source_path=request.git_url,
            workspace_path=workspace_path,
        )

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

