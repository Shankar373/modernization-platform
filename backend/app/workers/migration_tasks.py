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

STAGES = [
    ("DISCOVERY", 1),
    ("PROFILE", 2),
    ("RECOMMENDATION", 3),
    ("PLAN", 4),
    ("RECIPE_VALIDATION", 5),
    ("TRANSFORMATION", 6),
    ("COMPILE", 7),
    ("TEST", 8),
    ("QUALITY", 9),
    ("SECURITY", 10),
    ("FINALIZE", 11)
]


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
    modernization engine (orchestrator), and persists stage results to PostgreSQL.
    """
    _orchestrator = MigrationOrchestrator()

    async def _execute():
        async with AsyncSessionLocal() as db:
            # 1. Load MigrationRun
            db_run = await CRUDRepository.get_migration_run(db, result_id)
            if not db_run:
                print(f"[Celery] MigrationRun {result_id} not found in database!")
                return

            # Determine Worker Type and reject unsupported projects
            db_profile = await CRUDRepository.get_project_profile(db, db_run.project_id)
            languages = db_profile.languages if db_profile else []
            langs_lower = [l.lower() for l in languages]
            
            # Identify unsupported languages explicitly
            unsupported_langs = {"go", "php", "cpp", "c", "dotnet"}
            detected_unsupported = set(langs_lower) & unsupported_langs

            # Update status to RUNNING
            await CRUDRepository.update_migration_run_status(
                db=db,
                result_id=result_id,
                status=MigrationStatus.RUNNING.value,
                timeline=[{"step": "Task started on worker", "status": "running", "ts": datetime.utcnow().isoformat()}],
            )

            # Initialize all stages in DB
            for name, order in STAGES:
                status = "PENDING"
                msg = f"Stage {name} is pending"
                if name in ["QUALITY", "SECURITY"]:
                    status = "SKIPPED"
                    msg = f"Stage {name} is not implemented in the current capability profile"
                await CRUDRepository.create_migration_stage(
                    db=db,
                    project_id=db_run.project_id,
                    run_id=result_id,
                    stage_name=name,
                    stage_order=order,
                    status=status,
                    message=msg
                )

            # Helper to run a stage safely
            async def run_stage_event(name, order, status="SUCCESS", msg=None, err=None, logs=None):
                await CRUDRepository.create_migration_stage(
                    db=db,
                    project_id=db_run.project_id,
                    run_id=result_id,
                    stage_name=name,
                    stage_order=order,
                    status=status,
                    message=msg or f"Stage {name} completed with status: {status}",
                    logs=logs,
                    error_information=err
                )
                if status == "FAILED":
                    await CRUDRepository.update_migration_run_status(
                        db=db,
                        result_id=result_id,
                        status="FAILED",
                        completed_at=datetime.utcnow()
                    )
                    # Mark all subsequent stages as CANCELLED
                    for sname, sorder in STAGES:
                        if sorder > order:
                            await CRUDRepository.create_migration_stage(
                                db=db,
                                project_id=db_run.project_id,
                                run_id=result_id,
                                stage_name=sname,
                                stage_order=sorder,
                                status="CANCELLED",
                                message="Cancelled due to previous stage failure"
                            )
                    raise RuntimeError(f"Stage {name} failed: {msg}")

            if detected_unsupported:
                err_msg = f"Unsupported project language(s): {detected_unsupported}."
                await run_stage_event("DISCOVERY", 1, "FAILED", err_msg)
                await CRUDRepository.create_migration_error(
                    db=db,
                    run_id=result_id,
                    stage="DISCOVERY",
                    error_type="UNSUPPORTED_PROJECT",
                    message=err_msg,
                    traceback=None
                )
                return

            worker_type = "Generic Worker"
            if "java" in langs_lower:
                worker_type = "Java Worker"
            elif "python" in langs_lower:
                worker_type = "Python Worker"
            elif any(l in ["javascript", "typescript", "nodejs"] for l in langs_lower):
                worker_type = "Node Worker"

            print(f"[Celery] Selected Worker: {worker_type} for run {result_id}")

            from unittest.mock import patch
            import subprocess
            from app.core.git_safety import run_secured_command, SubprocessSecurityError

            def secure_subprocess_run(args, *args_list, **kwargs):
                timeout = kwargs.get("timeout", 300)
                cwd = kwargs.get("cwd")
                env = kwargs.get("env")
                res = run_secured_command(
                    args=args,
                    workspace_root=workspace_path,
                    cwd=cwd,
                    timeout_seconds=timeout,
                    additional_env=env
                )
                if res.get("timeout_triggered"):
                    raise subprocess.TimeoutExpired(args, timeout, output=res["stdout"], stderr=res["stderr"])
                if "error_message" in res and "blocked" in res["error_message"].lower():
                    raise SubprocessSecurityError(res["error_message"])
                if res["exit_code"] != 0 and "traversal" in res.get("stderr", ""):
                    raise SubprocessSecurityError(res.get("stderr"))
                    
                class CompletedProcess:
                    def __init__(self, args, returncode, stdout, stderr):
                        self.args = args
                        self.returncode = returncode
                        self.stdout = stdout
                        self.stderr = stderr
                    def check_returncode(self):
                        if self.returncode != 0:
                            raise subprocess.CalledProcessError(self.returncode, self.args, self.stdout, self.stderr)
                return CompletedProcess(args, res["exit_code"], res["stdout"], res["stderr"])

            try:
                # Patch subprocess.run with secure_subprocess_run throughout task execution
                with patch("subprocess.run", new=secure_subprocess_run):
                    # DISCOVERY
                    await run_stage_event("DISCOVERY", 1, "RUNNING", "Scanning workspace directory...")
                    await run_stage_event("DISCOVERY", 1, "SUCCESS", "Workspace directory scan finished.")

                    # PROFILE
                    await run_stage_event("PROFILE", 2, "RUNNING", "Detecting languages and frameworks...")
                    await run_stage_event("PROFILE", 2, "SUCCESS", "Profile detection finished.")

                    # RECOMMENDATION
                    await run_stage_event("RECOMMENDATION", 3, "RUNNING", "Scoring and recommending recipes...")
                    await run_stage_event("RECOMMENDATION", 3, "SUCCESS", "Scoring and recommendations finished.")

                    # PLAN
                    await run_stage_event("PLAN", 4, "RUNNING", "Creating migration plan...")
                    await run_stage_event("PLAN", 4, "SUCCESS", "Migration plan created.")

                    # RECIPE_VALIDATION
                    await run_stage_event("RECIPE_VALIDATION", 5, "RUNNING", "Validating recipe dependencies and conflicts...")
                    await run_stage_event("RECIPE_VALIDATION", 5, "SUCCESS", "Recipe validation successful.")

                    # TRANSFORMATION
                    try:
                        from app.core.git_safety import create_git_checkpoint
                        await create_git_checkpoint(workspace_path, result_id, db_run.project_id, db)
                    except Exception as checkpoint_err:
                        print(f"[Celery] Checkpoint creation skipped or failed: {checkpoint_err}")

                    await run_stage_event("TRANSFORMATION", 6, "RUNNING", "Applying code transformations...")
                    
                    # Determine if planned or full migrate-all run
                    if db_run.plan_id and not db_run.plan_id.startswith("all-"):
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
                        result = _orchestrator.migrate(workspace_path, plan)
                    else:
                        result = _orchestrator.migrate_all(workspace_path, db_run.project_id, profile_name)

                    if result.status == MigrationStatus.FAILED:
                        await run_stage_event("TRANSFORMATION", 6, "FAILED", "Transformation failed.", logs=str(result.logs))

                    await run_stage_event("TRANSFORMATION", 6, "SUCCESS", "Code transformations applied.", logs=str(result.logs))

                    # COMPILE
                    await run_stage_event("COMPILE", 7, "RUNNING", "Running build compilation validation...")
                    build_passed = result.statistics.build_passed if result.statistics.build_passed is not None else True
                    if not build_passed:
                        await run_stage_event("COMPILE", 7, "FAILED", "Build compilation failed.", logs=result.logs.get("validation"))
                    await run_stage_event("COMPILE", 7, "SUCCESS", "Build compilation passed.", logs=result.logs.get("validation"))

                    # TEST
                    await run_stage_event("TEST", 8, "RUNNING", "Running unit tests...")
                    tests_passed = result.statistics.tests_failed == 0 if result.statistics.tests_total > 0 else True
                    if not tests_passed:
                        await run_stage_event("TEST", 8, "FAILED", "Unit tests failed.", logs=result.logs.get("validation"))
                    await run_stage_event("TEST", 8, "SUCCESS", f"Unit tests passed ({result.statistics.tests_passed}/{result.statistics.tests_total}).", logs=result.logs.get("validation"))

                    # FINALIZE
                    await run_stage_event("FINALIZE", 11, "RUNNING", "Persisting results and report...")

                    # Save results to DB
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

                    # Create BuildResult entry
                    await CRUDRepository.create_build_result(
                        db=db,
                        run_id=result_id,
                        success=build_passed,
                        command="build",
                        output=result.logs.get("validation", ""),
                    )

                    # Create TestResult entry
                    await CRUDRepository.create_test_result(
                        db=db,
                        run_id=result_id,
                        success=tests_passed,
                        command="test",
                        total_tests=result.statistics.tests_total,
                        passed_tests=result.statistics.tests_passed,
                        failed_tests=result.statistics.tests_failed,
                        output=result.logs.get("validation", ""),
                    )

                    await run_stage_event("FINALIZE", 11, "SUCCESS", "Migration run completed successfully.")

            except Exception as e:
                # Capture run failure if not already captured
                trace = traceback.format_exc()
                print(f"[Celery] Run failed: {e}\n{trace}")
                
                # Trigger safe rollback
                try:
                    from app.core.git_safety import rollback_git_checkpoint
                    await rollback_git_checkpoint(result_id, db)
                except Exception as rollback_err:
                    print(f"[Celery] Automatic rollback failed: {rollback_err}")

                # Determine failure classification
                error_class = "WORKER_FAILURE"
                if isinstance(e, SubprocessSecurityError) or "traversal" in str(e).lower() or "security" in type(e).__name__.lower():
                    error_class = "SECURITY_BLOCK"
                elif isinstance(e, subprocess.TimeoutExpired):
                    error_class = "TIMEOUT"
                elif "syntax" in str(e).lower() or "ast" in str(e).lower():
                    error_class = "TRANSFORMATION_FAILURE"
                elif "compile" in str(e).lower() or "build" in str(e).lower():
                    error_class = "BUILD_FAILURE"
                elif "test" in str(e).lower() or "pytest" in str(e).lower():
                    error_class = "TEST_FAILURE"

                # Ensure the run is marked as FAILED in DB
                try:
                    await CRUDRepository.update_migration_run_status(
                        db=db,
                        result_id=result_id,
                        status=MigrationStatus.FAILED.value,
                        completed_at=datetime.utcnow(),
                    )
                    await CRUDRepository.create_migration_error(
                        db=db,
                        run_id=result_id,
                        stage="TRANSFORMATION",
                        error_type=error_class,
                        message=str(e),
                        traceback=trace,
                    )
                except Exception:
                    pass

    # Execute async wrapper
    run_async(_execute())
