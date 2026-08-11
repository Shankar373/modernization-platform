"""Migration API — plan, dry run, approve, execute, report."""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.domain.models import MigrationProfile
from app.core.orchestration.orchestrator import MigrationOrchestrator
from app.discovery.scanner import UniversalScanner

router = APIRouter()
_orchestrator = MigrationOrchestrator()
_scanner = UniversalScanner()

# In-memory plan store (replace with DB in production)
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
        result = _orchestrator.migrate(
            workspace_path=plan_data["workspace_path"],
            plan=plan_data["plan"],
        )
        _results[result.result_id] = {"result": result, "plan_data": plan_data}
        return result.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Migration failed: {e}")


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
