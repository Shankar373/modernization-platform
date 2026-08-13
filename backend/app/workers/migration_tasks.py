"""Celery background tasks for asynchronous migration execution."""
import asyncio
import traceback
from datetime import datetime
from app.workers.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.db.crud import CRUDRepository
from app.core.orchestration.orchestrator import MigrationOrchestrator
from app.core.domain.models import (
    MigrationPlan as ModelMigrationPlan,
    MigrationStatus,
    MigrationStatistics,
    FileChangeMetadata,
)


def run_async(coro):
    """Helper to run async coroutines synchronously in Celery worker."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@celery_app.task(name="app.workers.migration_tasks.run_migration_task")
def run_migration_task(result_id: str, workspace_path: str, plan_id: str = None, project_id: str = None, profile_name: str = "STANDARD"):
    """
    Background Celery task that loads the migration run state, executes the
    modernization engine (orchestrator), and persists results to PostgreSQL.
    """
    _orchestrator = MigrationOrchestrator()

    async def _execute():
        async with AsyncSessionLocal() as db:
            # 1. Load MigrationRun
            db_run = await CRUDRepository.get_migration_run(db, result_id)
            if not db_run:
                print(f"[Celery] MigrationRun {result_id} not found in database!")
                return

            # Update status to RUNNING
            await CRUDRepository.update_migration_run_status(
                db=db,
                result_id=result_id,
                status=MigrationStatus.RUNNING.value,
                timeline=[{"step": "Task started on worker", "status": "running", "ts": datetime.utcnow().isoformat()}],
            )

            try:
                # 2. Stage event: TRANSFORMATION running
                await CRUDRepository.create_migration_stage(
                    db=db,
                    project_id=db_run.project_id,
                    run_id=result_id,
                    stage_name="TRANSFORMATION",
                    status="RUNNING",
                )

                # 3. Determine if planned or full migrate-all run
                if db_run.plan_id and not db_run.plan_id.startswith("all-"):
                    # Planned migration
                    db_plan = await CRUDRepository.get_migration_plan(db, db_run.plan_id)
                    if not db_plan:
                        raise ValueError(f"MigrationPlan {db_run.plan_id} not found in database.")

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
                    # Run orchestrator
                    result = _orchestrator.migrate(workspace_path, plan)
                else:
                    # Full migrate-all run
                    result = _orchestrator.migrate_all(workspace_path, db_run.project_id, profile_name)

                # 4. Save results to DB
                await CRUDRepository.update_migration_run_status(
                    db=db,
                    result_id=result_id,
                    status=result.status.value,
                    statistics=result.statistics.model_dump(),
                    changed_files=[f.model_dump() for f in result.changed_files],
                    timeline=result.timeline,
                    logs=result.logs,
                    completed_at=datetime.utcnow(),
                )

                # Complete stage status
                await CRUDRepository.create_migration_stage(
                    db=db,
                    project_id=db_run.project_id,
                    run_id=result_id,
                    stage_name="TRANSFORMATION",
                    status=result.status.value,
                    logs=str(result.logs),
                )

                # Create BuildResult entry
                await CRUDRepository.create_build_result(
                    db=db,
                    run_id=result_id,
                    success=result.statistics.build_passed if result.statistics.build_passed is not None else True,
                    command="build",
                    output=result.logs.get("validation", ""),
                )

                # Create TestResult entry
                await CRUDRepository.create_test_result(
                    db=db,
                    run_id=result_id,
                    success=result.statistics.tests_failed == 0 if result.statistics.tests_total > 0 else True,
                    command="test",
                    total_tests=result.statistics.tests_total,
                    passed_tests=result.statistics.tests_passed,
                    failed_tests=result.statistics.tests_failed,
                    output=result.logs.get("validation", ""),
                )

            except Exception as e:
                # Mark as FAILED and save error
                trace = traceback.format_exc()
                await CRUDRepository.update_migration_run_status(
                    db=db,
                    result_id=result_id,
                    status=MigrationStatus.FAILED.value,
                    completed_at=datetime.utcnow(),
                )
                await CRUDRepository.create_migration_stage(
                    db=db,
                    project_id=db_run.project_id,
                    run_id=result_id,
                    stage_name="TRANSFORMATION",
                    status="FAILED",
                    logs=str(e),
                )
                await CRUDRepository.create_migration_error(
                    db=db,
                    run_id=result_id,
                    stage="TRANSFORMATION",
                    error_type=type(e).__name__,
                    message=str(e),
                    traceback=trace,
                )

    # Execute async wrapper
    run_async(_execute())
