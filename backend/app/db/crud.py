"""Database CRUD operations for Phase 1 persistence."""
from typing import Optional, List, Dict, Any
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import (
    DBProject,
    DBProjectProfile,
    DBMigrationPlan,
    DBMigrationRun,
    DBMigrationStage,
    DBMigrationCheckpoint,
    DBRecipeExecution,
    DBBuildResult,
    DBTestResult,
    DBMigrationError,
    DBMigrationReport,
)


class CRUDRepository:
    """Helper repository class for database persistence."""

    # ── Project ───────────────────────────────────────────────────────────────
    @staticmethod
    async def create_project(
        db: AsyncSession,
        project_id: str,
        name: str,
        source_type: str,
        source_path: str,
        workspace_path: str,
    ) -> DBProject:
        db_proj = DBProject(
            project_id=project_id,
            name=name,
            source_type=source_type,
            source_path=source_path,
            workspace_path=workspace_path,
        )
        db.add(db_proj)
        await db.commit()
        await db.refresh(db_proj)
        return db_proj

    @staticmethod
    async def get_project(db: AsyncSession, project_id: str) -> Optional[DBProject]:
        result = await db.execute(select(DBProject).filter(DBProject.project_id == project_id))
        return result.scalars().first()

    # ── ProjectProfile ────────────────────────────────────────────────────────
    @staticmethod
    async def create_project_profile(
        db: AsyncSession,
        project_id: str,
        profile_data: Dict[str, Any]
    ) -> DBProjectProfile:
        db_profile = DBProjectProfile(
            project_id=project_id,
            languages=profile_data.get("languages", []),
            frameworks=profile_data.get("frameworks", []),
            build_systems=profile_data.get("build_systems", []),
            dependencies=profile_data.get("dependencies", []),
            databases=profile_data.get("databases", []),
            testing_frameworks=profile_data.get("testing_frameworks", []),
            frontend_technologies=profile_data.get("frontend_technologies", []),
            file_count=profile_data.get("file_count", 0),
            total_lines=profile_data.get("total_lines", 0),
            is_multi_language=profile_data.get("is_multi_language", False),
            raw_scan_metadata=profile_data.get("raw_scan_metadata", {}),
        )
        db.add(db_profile)
        await db.commit()
        await db.refresh(db_profile)
        return db_profile

    @staticmethod
    async def get_project_profile(db: AsyncSession, project_id: str) -> Optional[DBProjectProfile]:
        result = await db.execute(select(DBProjectProfile).filter(DBProjectProfile.project_id == project_id))
        return result.scalars().first()

    # ── MigrationPlan ─────────────────────────────────────────────────────────
    @staticmethod
    async def create_migration_plan(
        db: AsyncSession,
        plan_id: str,
        project_id: str,
        profile: str,
        targets: List[Dict[str, Any]],
        steps: List[Dict[str, Any]],
        selected_capabilities: List[str],
        overall_risk: str,
        dry_run_available: bool = True,
        requires_approval: bool = True,
    ) -> DBMigrationPlan:
        db_plan = DBMigrationPlan(
            plan_id=plan_id,
            project_id=project_id,
            profile=profile,
            targets=targets,
            steps=steps,
            selected_capabilities=selected_capabilities,
            overall_risk=overall_risk,
            dry_run_available=dry_run_available,
            requires_approval=requires_approval,
        )
        db.add(db_plan)
        await db.commit()
        await db.refresh(db_plan)
        return db_plan

    @staticmethod
    async def get_migration_plan(db: AsyncSession, plan_id: str) -> Optional[DBMigrationPlan]:
        result = await db.execute(select(DBMigrationPlan).filter(DBMigrationPlan.plan_id == plan_id))
        return result.scalars().first()

    # ── MigrationRun ──────────────────────────────────────────────────────────
    @staticmethod
    async def create_migration_run(
        db: AsyncSession,
        result_id: str,
        job_id: str,
        project_id: str,
        plan_id: str,
        status: str,
        statistics: Dict[str, Any],
        changed_files: List[Dict[str, Any]],
        timeline: List[Dict[str, Any]],
        warnings: List[str],
        manual_remediation: List[str],
        logs: Dict[str, str],
        output_bundle_path: Optional[str] = None,
    ) -> DBMigrationRun:
        db_run = DBMigrationRun(
            result_id=result_id,
            job_id=job_id,
            project_id=project_id,
            plan_id=plan_id,
            status=status,
            statistics=statistics,
            changed_files=changed_files,
            timeline=timeline,
            warnings=warnings,
            manual_remediation=manual_remediation,
            logs=logs,
            output_bundle_path=output_bundle_path,
        )
        db.add(db_run)
        await db.commit()
        await db.refresh(db_run)
        return db_run

    @staticmethod
    async def update_migration_run_status(
        db: AsyncSession,
        result_id: str,
        status: str,
        statistics: Optional[Dict[str, Any]] = None,
        changed_files: Optional[List[Dict[str, Any]]] = None,
        timeline: Optional[List[Dict[str, Any]]] = None,
        logs: Optional[Dict[str, str]] = None,
        completed_at: Optional[Any] = None,
    ) -> Optional[DBMigrationRun]:
        db_run = await CRUDRepository.get_migration_run(db, result_id)
        if db_run:
            db_run.status = status
            if statistics is not None:
                db_run.statistics = statistics
            if changed_files is not None:
                db_run.changed_files = changed_files
            if timeline is not None:
                db_run.timeline = timeline
            if logs is not None:
                db_run.logs = logs
            if completed_at is not None:
                db_run.completed_at = completed_at
            await db.commit()
            await db.refresh(db_run)
        return db_run

    @staticmethod
    async def get_migration_run(db: AsyncSession, result_id: str) -> Optional[DBMigrationRun]:
        result = await db.execute(select(DBMigrationRun).filter(DBMigrationRun.result_id == result_id))
        return result.scalars().first()

    # ── MigrationStage ────────────────────────────────────────────────────────
    @staticmethod
    async def create_migration_stage(
        db: AsyncSession,
        project_id: str,
        stage_name: str,
        status: str,
        run_id: Optional[str] = None,
        stage_order: int = 0,
        duration: int = 0,
        progress: int = 0,
        message: Optional[str] = None,
        logs: Optional[str] = None,
        structured_results: Optional[Dict[str, Any]] = None,
        error_information: Optional[str] = None,
    ) -> DBMigrationStage:
        # Check if stage already exists for this run_id and name
        db_stage = None
        if run_id:
            result = await db.execute(
                select(DBMigrationStage).filter(
                    DBMigrationStage.run_id == run_id,
                    DBMigrationStage.stage_name == stage_name
                )
            )
            db_stage = result.scalars().first()

        if db_stage:
            db_stage.status = status
            if logs is not None:
                db_stage.logs = logs
            if structured_results is not None:
                db_stage.structured_results = structured_results
            if error_information is not None:
                db_stage.error_information = error_information
            if stage_order != 0:
                db_stage.stage_order = stage_order
            if duration != 0:
                db_stage.duration = duration
            if progress != 0:
                db_stage.progress = progress
            if message is not None:
                db_stage.message = message
            if status in ["SUCCESS", "FAILED"] and db_stage.start_time:
                db_stage.end_time = datetime.utcnow()
                db_stage.duration = int((db_stage.end_time - db_stage.start_time).total_seconds())
        else:
            db_stage = DBMigrationStage(
                project_id=project_id,
                run_id=run_id,
                stage_name=stage_name,
                stage_order=stage_order,
                status=status,
                duration=duration,
                progress=progress,
                message=message,
                logs=logs,
                structured_results=structured_results,
                error_information=error_information,
            )
            db.add(db_stage)

        await db.commit()
        await db.refresh(db_stage)
        return db_stage

    @staticmethod
    async def get_migration_stages(db: AsyncSession, run_id: str) -> List[DBMigrationStage]:
        result = await db.execute(
            select(DBMigrationStage)
            .filter(DBMigrationStage.run_id == run_id)
            .order_by(DBMigrationStage.stage_order.asc())
        )
        return list(result.scalars().all())

    # ── MigrationCheckpoint ───────────────────────────────────────────────────
    @staticmethod
    async def create_migration_checkpoint(
        db: AsyncSession,
        project_id: str,
        run_id: str,
        commit_sha: str,
        description: str,
        branch: Optional[str] = None,
        repository_path: Optional[str] = None,
        repository_status: Optional[str] = None,
        rollback_status: str = "NOT_REQUIRED",
    ) -> DBMigrationCheckpoint:
        db_cp = DBMigrationCheckpoint(
            project_id=project_id,
            run_id=run_id,
            commit_sha=commit_sha,
            description=description,
            branch=branch,
            repository_path=repository_path,
            repository_status=repository_status,
            rollback_status=rollback_status,
        )
        db.add(db_cp)
        await db.commit()
        await db.refresh(db_cp)
        return db_cp

    @staticmethod
    async def get_migration_checkpoints(db: AsyncSession, run_id: str) -> List[DBMigrationCheckpoint]:
        result = await db.execute(
            select(DBMigrationCheckpoint)
            .filter(DBMigrationCheckpoint.run_id == run_id)
            .order_by(DBMigrationCheckpoint.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def update_checkpoint_rollback_status(
        db: AsyncSession,
        checkpoint_id: str,
        status: str,
        error: Optional[str] = None
    ) -> Optional[DBMigrationCheckpoint]:
        result = await db.execute(
            select(DBMigrationCheckpoint).filter(DBMigrationCheckpoint.checkpoint_id == checkpoint_id)
        )
        db_cp = result.scalars().first()
        if db_cp:
            db_cp.rollback_status = status
            db_cp.rollback_timestamp = datetime.utcnow()
            if error:
                db_cp.rollback_error = error
            await db.commit()
            await db.refresh(db_cp)
        return db_cp

    # ── RecipeExecution ───────────────────────────────────────────────────────
    @staticmethod
    async def create_recipe_execution(
        db: AsyncSession,
        run_id: str,
        recipe_id: str,
        recipe_name: str,
        status: str,
        duration_ms: int = 0,
        logs: Optional[str] = None,
    ) -> DBRecipeExecution:
        db_exec = DBRecipeExecution(
            run_id=run_id,
            recipe_id=recipe_id,
            recipe_name=recipe_name,
            status=status,
            duration_ms=duration_ms,
            logs=logs,
        )
        db.add(db_exec)
        await db.commit()
        await db.refresh(db_exec)
        return db_exec

    # ── BuildResult ───────────────────────────────────────────────────────────
    @staticmethod
    async def create_build_result(
        db: AsyncSession,
        run_id: str,
        success: bool,
        command: str,
        output: Optional[str] = None,
    ) -> DBBuildResult:
        db_build = DBBuildResult(
            run_id=run_id,
            success=success,
            command=command,
            output=output,
        )
        db.add(db_build)
        await db.commit()
        await db.refresh(db_build)
        return db_build

    @staticmethod
    async def get_build_result(db: AsyncSession, run_id: str) -> Optional[DBBuildResult]:
        result = await db.execute(select(DBBuildResult).filter(DBBuildResult.run_id == run_id))
        return result.scalars().first()

    # ── TestResult ────────────────────────────────────────────────────────────
    @staticmethod
    async def create_test_result(
        db: AsyncSession,
        run_id: str,
        success: bool,
        command: str,
        total_tests: int = 0,
        passed_tests: int = 0,
        failed_tests: int = 0,
        output: Optional[str] = None,
    ) -> DBTestResult:
        db_test = DBTestResult(
            run_id=run_id,
            success=success,
            command=command,
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            output=output,
        )
        db.add(db_test)
        await db.commit()
        await db.refresh(db_test)
        return db_test

    @staticmethod
    async def get_test_result(db: AsyncSession, run_id: str) -> Optional[DBTestResult]:
        result = await db.execute(select(DBTestResult).filter(DBTestResult.run_id == run_id))
        return result.scalars().first()

    # ── MigrationError ────────────────────────────────────────────────────────
    @staticmethod
    async def create_migration_error(
        db: AsyncSession,
        run_id: str,
        stage: str,
        error_type: str,
        message: str,
        traceback: Optional[str] = None,
    ) -> DBMigrationError:
        db_err = DBMigrationError(
            run_id=run_id,
            stage=stage,
            error_type=error_type,
            message=message,
            traceback=traceback,
        )
        db.add(db_err)
        await db.commit()
        await db.refresh(db_err)
        return db_err

    @staticmethod
    async def get_migration_error(db: AsyncSession, run_id: str) -> Optional[DBMigrationError]:
        result = await db.execute(select(DBMigrationError).filter(DBMigrationError.run_id == run_id))
        return result.scalars().first()

    # ── MigrationReport ───────────────────────────────────────────────────────
    @staticmethod
    async def create_migration_report(
        db: AsyncSession,
        run_id: str,
        risk_level: str,
        summary: Optional[str] = None,
        full_report_json: Dict[str, Any] = None,
    ) -> DBMigrationReport:
        db_rep = DBMigrationReport(
            run_id=run_id,
            risk_level=risk_level,
            summary=summary,
            full_report_json=full_report_json or {},
        )
        db.add(db_rep)
        await db.commit()
        await db.refresh(db_rep)
        return db_rep

    @staticmethod
    async def get_migration_report(db: AsyncSession, run_id: str) -> Optional[DBMigrationReport]:
        result = await db.execute(select(DBMigrationReport).filter(DBMigrationReport.run_id == run_id))
        return result.scalars().first()

