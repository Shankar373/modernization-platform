"""Migration API — plan, dry run, approve, execute, report."""
import asyncio
import io
import re
import traceback
import uuid
import zipfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.domain.models import MigrationProfile
from app.core.orchestration.orchestrator import MigrationOrchestrator
from app.discovery.scanner import UniversalScanner

router = APIRouter()
_orchestrator = MigrationOrchestrator()
_scanner = UniversalScanner()

# In-memory plan/result store (replace with DB in production)
_plans: dict = {}
_results: dict = {}


class PlanRequest(BaseModel):
    workspace_path: str
    project_id: str
    language: str
    target_version: str
    migration_profile: MigrationProfile = MigrationProfile.CONSERVATIVE


class DryRunRequest(BaseModel):
    workspace_path: str
    plan_id: str


class ExecuteRequest(BaseModel):
    workspace_path: str
    plan_id: str
    approved: bool


class MigrateAllRequest(BaseModel):
    workspace_path: str
    project_id: str
    migration_profile: MigrationProfile = MigrationProfile.STANDARD


@router.post("/migration/plan")
async def create_migration_plan(request: PlanRequest):
    """Create a migration plan for the workspace."""
    try:
        profile = _scanner.scan(request.workspace_path)
        plan = _orchestrator.create_plan(
            workspace_path=request.workspace_path,
            profile=profile,
            language=request.language,
            target_version=request.target_version,
            migration_profile=request.migration_profile,
        )
        if not plan:
            raise HTTPException(
                status_code=400,
                detail=f"No migration adapter available for language: {request.language}",
            )
        _plans[plan.plan_id] = {"plan": plan, "workspace_path": request.workspace_path, "profile": profile}
        return plan.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Plan creation failed: {e}")


@router.post("/migration/dry-run")
async def dry_run(request: DryRunRequest):
    """Execute a dry run — preview what would change."""
    plan_data = _plans.get(request.plan_id)
    if not plan_data:
        raise HTTPException(status_code=404, detail="Plan not found.")
    try:
        result = _orchestrator.dry_run(
            workspace_path=plan_data["workspace_path"],
            plan=plan_data["plan"],
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dry run failed: {e}")


@router.post("/migration/execute")
async def execute_migration(request: ExecuteRequest):
    """Execute the migration. Requires explicit approval."""
    if not request.approved:
        raise HTTPException(status_code=400, detail="Migration requires explicit approval (approved=true).")

    plan_data = _plans.get(request.plan_id)
    if not plan_data:
        raise HTTPException(status_code=404, detail="Plan not found.")

    try:
        # Run blocking migration in a thread so the event loop stays free (fixes WinError 64)
        result = await asyncio.to_thread(
            _orchestrator.migrate,
            plan_data["workspace_path"],
            plan_data["plan"],
        )
        _results[result.result_id] = {"result": result, "plan_data": plan_data}
        return result.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Migration failed: {e}\n{traceback.format_exc()[:800]}")


@router.post("/migration/migrate-all")
async def migrate_all(request: MigrateAllRequest):
    """
    Full-application migration — auto-detects ALL languages and runs every
    applicable adapter (Python/ruff, HTML, CSS, JS/prettier, JSON, YAML, Markdown).
    Runs in a background thread via asyncio.to_thread() so the event loop
    stays unblocked (prevents WinError 64 / connection reset on Windows).
    """
    try:
        # ── Key fix: run the blocking sync function OFF the event loop thread ──
        # migrate_all() internally uses ThreadPoolExecutor; calling it directly
        # from an async handler blocks the ProactorEventLoop on Windows and
        # causes WinError 64 / connection resets.
        result = await asyncio.to_thread(
            _orchestrator.migrate_all,
            request.workspace_path,
            request.project_id,
            request.migration_profile,
        )
        _results[result.result_id] = {
            "result": result,
            "plan_data": {
                "workspace_path": request.workspace_path,
                "plan": None,
            },
        }
        return result.model_dump()
    except Exception as e:
        detail = f"Full-app migration failed: {e}\n{traceback.format_exc()[:1200]}"
        raise HTTPException(status_code=500, detail=detail)


@router.get("/migration/result/{result_id}")
async def get_result(result_id: str):
    """Get a migration result by ID."""
    result_data = _results.get(result_id)
    if not result_data:
        raise HTTPException(status_code=404, detail="Result not found.")
    return result_data["result"].model_dump()


@router.get("/migration/result/{result_id}/report")
async def get_report(result_id: str):
    """Generate and return the migration report."""
    result_data = _results.get(result_id)
    if not result_data:
        raise HTTPException(status_code=404, detail="Result not found.")
    try:
        report = _orchestrator.generate_report(
            workspace_path=result_data["plan_data"]["workspace_path"],
            plan=result_data["plan_data"]["plan"],
            result=result_data["result"],
        )
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {e}")


@router.get("/migration/result/{result_id}/files")
async def get_changed_files(result_id: str):
    """Return the list of changed files with diffs."""
    result_data = _results.get(result_id)
    if not result_data:
        raise HTTPException(status_code=404, detail="Result not found.")
    result = result_data["result"]
    return {
        "result_id": result_id,
        "changed_files": [f.model_dump() for f in result.changed_files],
        "statistics": result.statistics.model_dump(),
    }


def _is_uuid(val: str) -> bool:
    try:
        uuid.UUID(val)
        return True
    except ValueError:
        return False


def _resolve_project_name(ws: Path, result_obj: any) -> str:
    """Resolve original uploaded file name or Git repo name safely."""
    try:
        # 1. Saved .project_name file
        name_file = ws / ".project_name"
        if name_file.exists():
            val = name_file.read_text(encoding="utf-8").strip()
            if val and val != "unnamed" and not _is_uuid(val):
                return val

        # 2. Check single top-level directory inside workspace
        if ws.exists():
            subdirs = [d.name for d in ws.iterdir() if d.is_dir() and not d.name.startswith(".")]
            if len(subdirs) == 1:
                return subdirs[0]

        # 3. Non-UUID project_id
        pid = getattr(result_obj, "project_id", None) or (result_obj.get("project_id") if isinstance(result_obj, dict) else None)
        if pid and not _is_uuid(str(pid)):
            return str(pid)
    except Exception:
        pass

    return "modernized-application"


@router.get("/migration/result/{result_id}/download")
async def download_modernized_zip(result_id: str):
    """
    Download the modernized workspace as a ZIP file.
    The workspace contains all files after migration has been applied.
    """
    result_data = _results.get(result_id)
    if not result_data:
        raise HTTPException(status_code=404, detail="Result not found or server was restarted. Please re-run the migration.")

    try:
        workspace_path = result_data["plan_data"].get("workspace_path", "")
        ws = Path(workspace_path)
        if not ws.exists():
            raise HTTPException(status_code=404, detail="Workspace no longer exists — it may have been cleaned up.")

        _SKIP_IN_ZIP = {"__pycache__", "node_modules", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
        _SKIP_IN_ZIP_STARTS = {".git", ".venv", "venv", ".venv-broken"}

        # Resolve project name early so we can use it as the root folder prefix
        raw_name_pre = _resolve_project_name(ws, result_data.get("result"))
        clean_root = re.sub(r'[\(\)\s]+', '-', raw_name_pre).strip('-')
        clean_root = re.sub(r'[^a-zA-Z0-9_\-]', '', clean_root) or "application"
        # Remove any trailing -1 from ZIP filenames like 'architecture-discovery-main--1-'
        clean_root = re.sub(r'-+$', '', clean_root)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for file_path in sorted(ws.rglob("*")):
                if not file_path.is_file():
                    continue
                rel = file_path.relative_to(ws)
                parts = rel.parts
                # Skip hidden files like .project_name at root
                if parts[0].startswith('.'):
                    continue
                # Skip known build/tool directories
                if any(p in _SKIP_IN_ZIP for p in parts):
                    continue
                if any(p.startswith(tuple(_SKIP_IN_ZIP_STARTS)) for p in parts):
                    continue
                # Wrap inside original project root folder to preserve structure
                arcname = f"{clean_root}/{rel.as_posix()}"
                zf.write(file_path, arcname)
        buf.seek(0)

        # Use the same clean_root for the download filename
        if clean_root.lower().endswith("-modernized"):
            filename = f"{clean_root}.zip"
        else:
            filename = f"{clean_root}-modernized.zip"


        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {e}\n{traceback.format_exc()[:800]}")



