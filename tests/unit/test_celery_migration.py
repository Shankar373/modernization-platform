"""Unit tests for Celery initialization and task execution flow."""
import pytest
import uuid
from unittest.mock import MagicMock, patch
from app.workers.celery_app import celery_app
from app.workers.migration_tasks import run_migration_task
from app.core.domain.models import MigrationStatus, MigrationResult, MigrationStatistics


def test_celery_config():
    """Verify Celery app initialization and broker configuration."""
    assert celery_app.main == "modernization_platform"
    assert celery_app.conf.task_serializer == "json"
    assert "app.workers.migration_tasks" in celery_app.conf.include


@patch("app.workers.migration_tasks.CRUDRepository")
@patch("app.workers.migration_tasks.MigrationOrchestrator")
def test_migration_task_execution(mock_orch, mock_crud):
    """Verify Celery task loads DBMigrationRun and updates status."""
    result_id = str(uuid.uuid4())
    workspace_path = "/tmp/test-workspace"
    plan_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())

    # Mock DB run row
    from unittest.mock import AsyncMock
    mock_run = MagicMock()
    mock_run.result_id = result_id
    mock_run.plan_id = plan_id
    mock_run.project_id = project_id
    mock_crud.get_migration_run = AsyncMock(return_value=mock_run)

    # Mock project profile row (used by unsupported-language detection)
    mock_profile = MagicMock()
    mock_profile.languages = ["Python"]
    mock_crud.get_project_profile = AsyncMock(return_value=mock_profile)

    # Mock DB plan row
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

    # Mock Orchestrator result
    mock_result = MigrationResult(
        result_id=result_id,
        job_id=str(uuid.uuid4()),
        project_id=project_id,
        plan_id=plan_id,
        status=MigrationStatus.SUCCESS,
        statistics=MigrationStatistics(files_modified=5),
        timeline=[],
        warnings=[],
        manual_remediation=[],
        logs={},
    )
    mock_orch.return_value.migrate = MagicMock(return_value=mock_result)

    # Mock database session transactions
    from unittest.mock import AsyncMock
    with patch("app.workers.migration_tasks.AsyncSessionLocal") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock()

        # Run the celery task synchronously
        run_migration_task(result_id, workspace_path, plan_id, project_id, "STANDARD")

        # Verify DB updates were triggered
        assert mock_crud.update_migration_run_status.call_count >= 2
        assert mock_crud.create_migration_stage.call_count >= 2
