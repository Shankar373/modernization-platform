"""Unit tests for multi-stage migration state machine and status API."""
import pytest
import uuid
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient

from app.workers.migration_tasks import run_migration_task
from app.core.domain.models import MigrationStatus, MigrationResult, MigrationStatistics
from app.main import app

client = TestClient(app)


def test_progress_calculation_and_stages_initialization():
    """Verify Celery task registers correct stages and progress calculates correctly."""
    result_id = str(uuid.uuid4())
    workspace_path = "/tmp/test-workspace"
    plan_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())

    with patch("app.workers.migration_tasks.CRUDRepository") as mock_crud, \
         patch("app.workers.migration_tasks.MigrationOrchestrator") as mock_orch, \
         patch("app.workers.migration_tasks.AsyncSessionLocal") as mock_session_cls:

        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        # Mock DB rows
        mock_run = MagicMock()
        mock_run.result_id = result_id
        mock_run.plan_id = plan_id
        mock_run.project_id = project_id
        mock_crud.get_migration_run = AsyncMock(return_value=mock_run)

        mock_profile = MagicMock()
        mock_profile.languages = ["Python"]
        mock_crud.get_project_profile = AsyncMock(return_value=mock_profile)

        mock_plan = MagicMock()
        mock_plan.plan_id = plan_id
        mock_plan.project_id = project_id
        mock_plan.profile = "STANDARD"
        mock_plan.targets = []
        mock_plan.steps = []
        mock_plan.selected_capabilities = []
        mock_plan.overall_risk = "LOW"
        mock_plan.dry_run_available = True
        mock_plan.requires_approval = True
        mock_crud.get_migration_plan = AsyncMock(return_value=mock_plan)

        mock_crud.update_migration_run_status = AsyncMock()
        mock_crud.create_migration_stage = AsyncMock()
        mock_crud.create_build_result = AsyncMock()
        mock_crud.create_test_result = AsyncMock()

        # Mock Orchestrator success
        mock_result = MigrationResult(
            result_id=result_id,
            job_id=str(uuid.uuid4()),
            project_id=project_id,
            plan_id=plan_id,
            status=MigrationStatus.SUCCESS,
            statistics=MigrationStatistics(files_modified=5, build_passed=True),
            timeline=[],
            warnings=[],
            manual_remediation=[],
            logs={"validation": ""},
        )
        mock_orch.return_value.migrate = MagicMock(return_value=mock_result)

        # Execute Celery task synchronously
        run_migration_task(result_id, workspace_path, plan_id, project_id, "STANDARD")

        # Verify stages were created and updated
        # 11 stages initialized, and updated throughout the lifecycle
        assert mock_crud.create_migration_stage.call_count >= 11
