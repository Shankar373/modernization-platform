"""Migration API — plan, dry run, approve, execute, report."""
import asyncio
import io
import re
import traceback
import uuid
import zipfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain.models import MigrationProfile
from app.core.orchestration.orchestrator import MigrationOrchestrator
from app.discovery.scanner import UniversalScanner
from app.db.session import get_db
from app.db.crud import CRUDRepository

router = APIRouter()
_orchestrator = MigrationOrchestrator()
_scanner = UniversalScanner()

# In-memory caches (gradually migrating state to database)
_plans: dict = {}
_results: dict = {}
_dry_run_all_results: dict = {}   # stores dry-run-all previews keyed by project_id


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


class DryRunAllRequest(BaseModel):
    workspace_path: str
    project_id: str
    migration_profile: MigrationProfile = MigrationProfile.STANDARD


class ApproveAndExecuteRequest(BaseModel):
    """Accept the dry-run result and kick off the full migration."""
    workspace_path: str
    project_id: str
    migration_profile: MigrationProfile = MigrationProfile.STANDARD
    approved: bool = True


@router.post("/migration/plan")
async def create_migration_plan(request: PlanRequest, db: AsyncSession = Depends(get_db)):
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
        
        # Save to DB
        await CRUDRepository.create_migration_plan(
            db=db,
            plan_id=plan.plan_id,
            project_id=request.project_id,
            profile=request.migration_profile.value,
            targets=[t.model_dump() for t in plan.targets],
            steps=[s.model_dump() for s in plan.steps],
            selected_capabilities=plan.selected_capabilities,
            overall_risk=plan.overall_risk.value,
            dry_run_available=plan.dry_run_available,
            requires_approval=plan.requires_approval,
        )

        _plans[plan.plan_id] = {"plan": plan, "workspace_path": request.workspace_path, "profile": profile}
        return plan.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Plan creation failed: {e}")


@router.post("/migration/dry-run")
async def dry_run(request: DryRunRequest, db: AsyncSession = Depends(get_db)):
    """Execute a dry run — preview what would change."""
    db_plan = await CRUDRepository.get_migration_plan(db, request.plan_id)
    if db_plan:
        from app.core.domain.models import MigrationPlan as ModelMigrationPlan
        proj = await CRUDRepository.get_project(db, db_plan.project_id)
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found.")
        workspace_path = proj.workspace_path
        plan = ModelMigrationPlan(
            plan_id=db_plan.plan_id,
            project_id=db_plan.project_id,
            profile=db_plan.profile,
            targets=db_plan.targets,
            steps=db_plan.steps,
            selected_capabilities=db_plan.selected_capabilities,
            overall_risk=db_plan.overall_risk,
            dry_run_available=db_plan.dry_run_available,
            requires_approval=db_plan.requires_approval,
        )
    else:
        plan_data = _plans.get(request.plan_id)
        if not plan_data:
            raise HTTPException(status_code=404, detail="Plan not found.")
        workspace_path = plan_data["workspace_path"]
        plan = plan_data["plan"]

    try:
        result = _orchestrator.dry_run(
            workspace_path=workspace_path,
            plan=plan,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dry run failed: {e}")


@router.post("/migration/execute")
async def execute_migration(request: ExecuteRequest, db: AsyncSession = Depends(get_db)):
    """Execute the migration. Requires explicit approval."""
    if not request.approved:
        raise HTTPException(status_code=400, detail="Migration requires explicit approval (approved=true).")

    db_plan = await CRUDRepository.get_migration_plan(db, request.plan_id)
    if db_plan:
        from app.core.domain.models import MigrationPlan as ModelMigrationPlan
        proj = await CRUDRepository.get_project(db, db_plan.project_id)
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found.")
        workspace_path = proj.workspace_path
        project_id = db_plan.project_id
        profile_name = db_plan.profile
    else:
        plan_data = _plans.get(request.plan_id)
        if not plan_data:
            raise HTTPException(status_code=404, detail="Plan not found.")
        workspace_path = plan_data["workspace_path"]
        project_id = plan_data["plan"].project_id
        profile_name = plan_data["plan"].profile.value

    try:
        from datetime import datetime
        result_id = str(uuid.uuid4())
        job_id = str(uuid.uuid4())

        # Save QUEUED run to DB
        await CRUDRepository.create_migration_run(
            db=db,
            result_id=result_id,
            job_id=job_id,
            project_id=project_id,
            plan_id=request.plan_id,
            status="QUEUED",
            statistics={},
            changed_files=[],
            timeline=[{"step": "Queued in database", "status": "queued", "ts": datetime.utcnow().isoformat()}],
            warnings=[],
            manual_remediation=[],
            logs={},
        )

        # Create stage status
        await CRUDRepository.create_migration_stage(
            db=db,
            project_id=project_id,
            run_id=result_id,
            stage_name="TRANSFORMATION",
            status="QUEUED",
        )

        # Submit background task
        from app.workers.migration_tasks import run_migration_task
        run_migration_task.delay(result_id, workspace_path, request.plan_id, project_id, profile_name)

        return {
            "result_id": result_id,
            "job_id": job_id,
            "project_id": project_id,
            "plan_id": request.plan_id,
            "status": "QUEUED",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Migration queueing failed: {e}\n{traceback.format_exc()[:800]}")


@router.post("/migration/dry-run-all")
async def dry_run_all(request: DryRunAllRequest):
    """
    Preview ALL adapters in parallel without modifying any files.
    Returns a per-adapter breakdown of what would change.
    The result is cached by project_id so /migration/approve-execute can
    immediately kick off the migration when the user accepts.
    """
    try:
        preview = await asyncio.to_thread(
            _orchestrator.dry_run_all,
            request.workspace_path,
            request.project_id,
            request.migration_profile,
        )
        # Cache for the approve step
        _dry_run_all_results[request.project_id] = {
            "preview": preview,
            "workspace_path": request.workspace_path,
            "migration_profile": request.migration_profile,
        }
        return preview
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dry-run-all failed: {e}\n{traceback.format_exc()[:800]}")


@router.post("/migration/approve-execute")
async def approve_and_execute(request: ApproveAndExecuteRequest, db: AsyncSession = Depends(get_db)):
    """
    User accepted the dry-run preview — now execute the full migration.
    Runs all adapters in parallel (same as migrate-all) and stores the result.
    Requires approved=true for an explicit user confirmation gate.
    """
    if not request.approved:
        raise HTTPException(status_code=400, detail="Execution requires explicit approval (approved=true).")
    try:
        result_id = str(uuid.uuid4())
        job_id = str(uuid.uuid4())
        plan_id = f"all-{result_id}"

        # Save QUEUED run to database
        await CRUDRepository.create_migration_run(
            db=db,
            result_id=result_id,
            job_id=job_id,
            project_id=request.project_id,
            plan_id=plan_id,
            status="QUEUED",
            statistics={},
            changed_files=[],
            timeline=[{"step": "Queued in database", "status": "queued", "ts": datetime.utcnow().isoformat()}],
            warnings=[],
            manual_remediation=[],
            logs={},
        )

        # Create QUEUED stage status
        await CRUDRepository.create_migration_stage(
            db=db,
            project_id=request.project_id,
            run_id=result_id,
            stage_name="TRANSFORMATION",
            status="QUEUED",
        )

        # Clean up the dry-run cache
        _dry_run_all_results.pop(request.project_id, None)

        # Trigger background task
        from app.workers.migration_tasks import run_migration_task
        run_migration_task.delay(result_id, request.workspace_path, plan_id, request.project_id, request.migration_profile.value)

        return {
            "result_id": result_id,
            "job_id": job_id,
            "project_id": request.project_id,
            "plan_id": plan_id,
            "status": "QUEUED",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Approved execution queuing failed: {e}\n{traceback.format_exc()[:1200]}"
        )


@router.post("/migration/migrate-all")
async def migrate_all(request: MigrateAllRequest, db: AsyncSession = Depends(get_db)):
    """
    Full-application migration — auto-detects ALL languages and runs every
    applicable adapter (Python/ruff, HTML, CSS, JS/prettier, JSON, YAML, Markdown).
    """
    try:
        result_id = str(uuid.uuid4())
        job_id = str(uuid.uuid4())
        plan_id = f"all-{result_id}"

        # Save QUEUED run to database
        await CRUDRepository.create_migration_run(
            db=db,
            result_id=result_id,
            job_id=job_id,
            project_id=request.project_id,
            plan_id=plan_id,
            status="QUEUED",
            statistics={},
            changed_files=[],
            timeline=[{"step": "Queued in database", "status": "queued", "ts": datetime.utcnow().isoformat()}],
            warnings=[],
            manual_remediation=[],
            logs={},
        )

        # Create QUEUED stage status
        await CRUDRepository.create_migration_stage(
            db=db,
            project_id=request.project_id,
            run_id=result_id,
            stage_name="TRANSFORMATION",
            status="QUEUED",
        )

        # Trigger background task
        from app.workers.migration_tasks import run_migration_task
        run_migration_task.delay(result_id, request.workspace_path, plan_id, request.project_id, request.migration_profile.value)

        return {
            "result_id": result_id,
            "job_id": job_id,
            "project_id": request.project_id,
            "plan_id": plan_id,
            "status": "QUEUED",
        }
    except Exception as e:
        detail = f"Full-app migration queueing failed: {e}\n{traceback.format_exc()[:1200]}"
        raise HTTPException(status_code=500, detail=detail)


@router.get("/migration/result/{result_id}")
async def get_result(result_id: str, db: AsyncSession = Depends(get_db)):
    """Get a migration result by ID."""
    db_run = await CRUDRepository.get_migration_run(db, result_id)
    if db_run:
        return {
            "result_id": db_run.result_id,
            "job_id": db_run.job_id,
            "project_id": db_run.project_id,
            "plan_id": db_run.plan_id,
            "status": db_run.status,
            "completed_at": db_run.completed_at.isoformat() if db_run.completed_at else None,
            "statistics": db_run.statistics,
            "changed_files": db_run.changed_files,
            "timeline": db_run.timeline,
            "warnings": db_run.warnings,
            "manual_remediation": db_run.manual_remediation,
            "logs": db_run.logs,
            "output_bundle_path": db_run.output_bundle_path,
        }

    result_data = _results.get(result_id)
    if not result_data:
        raise HTTPException(status_code=404, detail="Result not found.")
    return result_data["result"].model_dump()


@router.get("/migration/{run_id}/status")
async def get_migration_status(run_id: str, db: AsyncSession = Depends(get_db)):
    """Get the persistent status of a migration run and its progression stages."""
    db_run = await CRUDRepository.get_migration_run(db, run_id)
    
    # Define fallback stages structure
    stages_fallback = [
        ("DISCOVERY", 1), ("PROFILE", 2), ("RECOMMENDATION", 3), ("PLAN", 4),
        ("RECIPE_VALIDATION", 5), ("TRANSFORMATION", 6), ("COMPILE", 7),
        ("TEST", 8), ("QUALITY", 9), ("SECURITY", 10), ("FINALIZE", 11)
    ]

    if not db_run:
        result_data = _results.get(run_id)
        if not result_data:
            raise HTTPException(status_code=404, detail="Migration run not found.")
        return {
            "run_id": run_id,
            "status": "SUCCESS",
            "current_stage": "FINALIZE",
            "progress": 100,
            "stages": [
                {"name": name, "status": "SUCCESS", "progress": 100, "message": "Completed", "duration": 0, "error_message": None}
                for name, _ in stages_fallback
            ]
        }

    db_stages = await CRUDRepository.get_migration_stages(db, run_id)
    applicable_stages = [s for s in db_stages if s.status != "PENDING"]
    completed_stages = [s for s in db_stages if s.status in ["SUCCESS", "SKIPPED"]]
    
    total_stages = len(db_stages) if db_stages else len(stages_fallback)
    progress_val = int((len(completed_stages) / total_stages) * 100) if total_stages > 0 else 0
    
    current_stage = "QUEUED"
    running_stages = [s for s in db_stages if s.status == "RUNNING"]
    if running_stages:
        current_stage = running_stages[0].stage_name
    elif applicable_stages:
        sorted_app = sorted(applicable_stages, key=lambda x: x.stage_order, reverse=True)
        current_stage = sorted_app[0].stage_name

    return {
        "run_id": db_run.result_id,
        "status": db_run.status,
        "current_stage": current_stage,
        "progress": progress_val,
        "stages": [
            {
                "name": s.stage_name,
                "status": s.status,
                "progress": s.progress,
                "message": s.message,
                "duration": s.duration,
                "error_message": s.error_information
            }
            for s in db_stages
        ]
    }


@router.get("/migration/{run_id}/checkpoints")
async def get_checkpoints(run_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieve Git checkpoints created during a migration run."""
    checkpoints = await CRUDRepository.get_migration_checkpoints(db, run_id)
    return [
        {
            "checkpoint_id": cp.checkpoint_id,
            "run_id": cp.run_id,
            "commit_sha": cp.commit_sha,
            "description": cp.description,
            "branch": cp.branch,
            "rollback_status": cp.rollback_status,
            "rollback_timestamp": cp.rollback_timestamp.isoformat() if cp.rollback_timestamp else None,
            "rollback_error": cp.rollback_error,
            "created_at": cp.created_at.isoformat() if cp.created_at else None
        }
        for cp in checkpoints
    ]


@router.post("/migration/{run_id}/rollback")
async def trigger_manual_rollback(run_id: str, db: AsyncSession = Depends(get_db)):
    """Manually revert the repository changes back to the pre-modernization checkpoint."""
    from app.core.git_safety import rollback_git_checkpoint
    res = await rollback_git_checkpoint(run_id, db)
    if res["status"] == "FAILED":
        raise HTTPException(status_code=400, detail=res["message"])
    elif res["status"] == "BLOCKED":
        raise HTTPException(status_code=403, detail=res["message"])
    return res





@router.get("/migration/result/{result_id}/report")
async def get_report(result_id: str, db: AsyncSession = Depends(get_db)):
    """Generate and return the migration report."""
    db_run = await CRUDRepository.get_migration_run(db, result_id)
    if db_run:
        proj = await CRUDRepository.get_project(db, db_run.project_id)
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found.")
        workspace_path = proj.workspace_path
        
        # Build pydantic models from db
        from app.core.domain.models import MigrationResult as ModelMigrationResult, MigrationStatistics, FileChangeMetadata
        result = ModelMigrationResult(
            result_id=db_run.result_id,
            job_id=db_run.job_id,
            project_id=db_run.project_id,
            plan_id=db_run.plan_id,
            status=db_run.status,
            completed_at=db_run.completed_at,
            statistics=MigrationStatistics(**db_run.statistics),
            changed_files=[FileChangeMetadata(**f) for f in db_run.changed_files],
            timeline=db_run.timeline,
            warnings=db_run.warnings,
            manual_remediation=db_run.manual_remediation,
            logs=db_run.logs,
            output_bundle_path=db_run.output_bundle_path,
        )
        
        # Optionally retrieve plan if it exists
        plan = None
        db_plan = await CRUDRepository.get_migration_plan(db, db_run.plan_id)
        if db_plan:
            from app.core.domain.models import MigrationPlan as ModelMigrationPlan
            plan = ModelMigrationPlan(
                plan_id=db_plan.plan_id,
                project_id=db_plan.project_id,
                profile=db_plan.profile,
                targets=db_plan.targets,
                steps=db_plan.steps,
                selected_capabilities=db_plan.selected_capabilities,
                overall_risk=db_plan.overall_risk,
                dry_run_available=db_plan.dry_run_available,
                requires_approval=db_plan.requires_approval,
            )
        
        try:
            report = _orchestrator.generate_report(
                workspace_path=workspace_path,
                plan=plan,
                result=result,
            )
            # Save report to DB
            await CRUDRepository.create_migration_report(
                db=db,
                run_id=result_id,
                risk_level=report.get("overall_risk", "MEDIUM"),
                summary=report.get("summary", ""),
                full_report_json=report,
            )
            return report
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Report generation failed: {e}")

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
async def get_changed_files(result_id: str, db: AsyncSession = Depends(get_db)):
    """Return the list of changed files with diffs."""
    db_run = await CRUDRepository.get_migration_run(db, result_id)
    if db_run:
        return {
            "result_id": result_id,
            "changed_files": db_run.changed_files,
            "statistics": db_run.statistics,
        }

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
async def download_modernized_zip(result_id: str, db: AsyncSession = Depends(get_db)):
    """
    Download the modernized workspace as a ZIP file.
    The workspace contains all files after migration has been applied.
    """
    db_run = await CRUDRepository.get_migration_run(db, result_id)
    if db_run:
        proj = await CRUDRepository.get_project(db, db_run.project_id)
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found.")
        workspace_path = proj.workspace_path
        result_obj = db_run
    else:
        result_data = _results.get(result_id)
        if not result_data:
            raise HTTPException(status_code=404, detail="Result not found or server was restarted. Please re-run the migration.")
        workspace_path = result_data["plan_data"].get("workspace_path", "")
        result_obj = result_data.get("result")

    try:
        ws = Path(workspace_path)
        if not ws.exists():
            raise HTTPException(status_code=404, detail="Workspace no longer exists — it may have been cleaned up.")

        _SKIP_IN_ZIP = {"__pycache__", "node_modules", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
        _SKIP_IN_ZIP_STARTS = {".git", ".venv", "venv", ".venv-broken"}

        # Resolve project name early so we can use it as the root folder prefix
        raw_name_pre = _resolve_project_name(ws, result_obj)
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



