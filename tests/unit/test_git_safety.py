"""Unit tests verifying all Phase 4 Git safety, validation, and rollback rules."""
import pytest
import os
import shutil
import tempfile
import git
from unittest.mock import MagicMock, AsyncMock, patch

from app.core.git_safety import (
    verify_workspace_is_git,
    get_repo_info,
    create_git_checkpoint,
    rollback_git_checkpoint,
)
from app.db.models import DBMigrationCheckpoint
from app.db.crud import CRUDRepository


@pytest.fixture
def temp_git_repo():
    """Fixture to create a temporary Git repository for testing."""
    temp_dir = tempfile.mkdtemp()
    repo = git.Repo.init(temp_dir)
    # Set dummy user details
    repo.config_writer().set_value("user", "name", "Test User").release()
    repo.config_writer().set_value("user", "email", "test@user.com").release()
    
    # Create an initial file and commit it
    test_file = os.path.join(temp_dir, "test.txt")
    with open(test_file, "w") as f:
        f.write("initial baseline content")
    repo.git.add(A=True)
    repo.git.commit(m="Initial Commit")
    
    yield temp_dir
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_dirty_repository_blocks_checkpoint(temp_git_repo):
    """Verify that a dirty workspace blocks checkpoint creation and throws RuntimeError."""
    db = MagicMock()
    # Create a dirty file (uncommitted changes)
    dirty_file = os.path.join(temp_git_repo, "dirty.txt")
    with open(dirty_file, "w") as f:
        f.write("uncommitted user changes")
        
    with pytest.raises(RuntimeError) as exc_info:
        await create_git_checkpoint(temp_git_repo, "run-1", "proj-1", db)
    
    assert "Workspace is dirty" in str(exc_info.value)


@pytest.mark.asyncio
async def test_user_modification_after_checkpoint_blocks_rollback(temp_git_repo):
    """Verify that unexpected user modifications after checkpoint creation blocks rollback."""
    db = MagicMock()
    run_id = "test-run-id"
    project_id = "test-project-id"

    # Create checkpoint on clean repository
    initial_sha = git.Repo(temp_git_repo).head.commit.hexsha
    mock_cp = DBMigrationCheckpoint(
        checkpoint_id="cp-id-123",
        project_id=project_id,
        run_id=run_id,
        commit_sha=initial_sha,
        description="Pre-transformation checkpoint",
        branch="master",
        repository_path=temp_git_repo,
        repository_status="clean",
        rollback_status="AVAILABLE",
    )

    # Mock DBMigrationRun with empty changed_files (no modifications made by SystemaOps)
    mock_run = MagicMock()
    mock_run.changed_files = []

    # User modifies a file manually
    test_file = os.path.join(temp_git_repo, "test.txt")
    with open(test_file, "w") as f:
        f.write("unexpected user change")

    with patch.object(CRUDRepository, "get_migration_checkpoints", AsyncMock(return_value=[mock_cp])), \
         patch.object(CRUDRepository, "update_checkpoint_rollback_status", AsyncMock()), \
         patch.object(CRUDRepository, "get_migration_run", AsyncMock(return_value=mock_run)):
        # Try rolling back - should be blocked because the change is unexpected
        res = await rollback_git_checkpoint(run_id, db)
        assert res["status"] == "BLOCKED"
        assert "Unexpected user changes detected" in res["message"]
    
    # Assert file is untouched and not deleted/reset
    with open(test_file, "r") as f:
        assert f.read() == "unexpected user change"


@pytest.mark.asyncio
async def test_safe_rollback_allowed_for_systemaops_changes(temp_git_repo):
    """Verify rollback works normally when modifications match allowed SystemaOps changes."""
    db = MagicMock()
    run_id = "test-run-id"
    project_id = "test-project-id"

    # Create checkpoint on clean repository
    initial_sha = git.Repo(temp_git_repo).head.commit.hexsha
    mock_cp = DBMigrationCheckpoint(
        checkpoint_id="cp-id-123",
        project_id=project_id,
        run_id=run_id,
        commit_sha=initial_sha,
        description="Pre-transformation checkpoint",
        branch="master",
        repository_path=temp_git_repo,
        repository_status="clean",
        rollback_status="AVAILABLE",
    )

    # Mock DBMigrationRun where changed_files contains the modified file
    mock_run = MagicMock()
    mock_run.changed_files = [{"file_path": "test.txt", "diff": "..."}]

    # SystemaOps modifies the file during transformation
    test_file = os.path.join(temp_git_repo, "test.txt")
    with open(test_file, "w") as f:
        f.write("systemaops modified content")

    with patch.object(CRUDRepository, "get_migration_checkpoints", AsyncMock(return_value=[mock_cp])), \
         patch.object(CRUDRepository, "update_checkpoint_rollback_status", AsyncMock()), \
         patch.object(CRUDRepository, "get_migration_run", AsyncMock(return_value=mock_run)):
        # Rollback should succeed since changes match allowed file list
        res = await rollback_git_checkpoint(run_id, db)
        assert res["status"] == "SUCCESS"

    # File should be reverted back to initial baseline content
    with open(test_file, "r") as f:
        assert f.read() == "initial baseline content"


@pytest.mark.asyncio
async def test_wrong_branch_blocks_rollback(temp_git_repo):
    """Verify that a branch mismatch blocks the rollback process."""
    db = MagicMock()
    run_id = "test-run-id"
    project_id = "test-project-id"

    # Mock checkpoint expecting "nonexistent-branch"
    mock_cp = DBMigrationCheckpoint(
        checkpoint_id="cp-id-123",
        project_id=project_id,
        run_id=run_id,
        commit_sha=git.Repo(temp_git_repo).head.commit.hexsha,
        description="Pre-transformation checkpoint",
        branch="nonexistent-branch",
        repository_path=temp_git_repo,
        repository_status="clean",
        rollback_status="AVAILABLE",
    )

    with patch.object(CRUDRepository, "get_migration_checkpoints", AsyncMock(return_value=[mock_cp])), \
         patch.object(CRUDRepository, "update_checkpoint_rollback_status", AsyncMock()):
        res = await rollback_git_checkpoint(run_id, db)
        assert res["status"] == "BLOCKED"
        assert "Branch mismatch" in res["message"]


@pytest.mark.asyncio
async def test_wrong_checkpoint_sha_fails_rollback(temp_git_repo):
    """Verify that an invalid or non-existent commit SHA fails rollback."""
    db = MagicMock()
    run_id = "test-run-id"
    project_id = "test-project-id"

    # Mock checkpoint with wrong SHA
    mock_cp = DBMigrationCheckpoint(
        checkpoint_id="cp-id-123",
        project_id=project_id,
        run_id=run_id,
        commit_sha="invalidsha1234567890abcdef1234567890",
        description="Pre-transformation checkpoint",
        branch="master",
        repository_path=temp_git_repo,
        repository_status="clean",
        rollback_status="AVAILABLE",
    )

    with patch.object(CRUDRepository, "get_migration_checkpoints", AsyncMock(return_value=[mock_cp])), \
         patch.object(CRUDRepository, "update_checkpoint_rollback_status", AsyncMock()):
        res = await rollback_git_checkpoint(run_id, db)
        assert res["status"] == "FAILED"
        assert "not found in history" in res["message"]


@pytest.mark.asyncio
async def test_checkpoint_creation_and_rollback(temp_git_repo):
    """Verify that checkpoint is created and rollback reverts modifications."""
    db = MagicMock()
    run_id = "test-run-id"
    project_id = "test-project-id"

    mock_cp = DBMigrationCheckpoint(
        checkpoint_id="cp-id-123",
        project_id=project_id,
        run_id=run_id,
        commit_sha=git.Repo(temp_git_repo).head.commit.hexsha,
        description="Pre-transformation checkpoint",
        branch="master",
        repository_path=temp_git_repo,
        repository_status="clean",
        rollback_status="AVAILABLE",
    )

    mock_run = MagicMock()
    mock_run.changed_files = [{"file_path": "test.txt", "diff": "..."}]

    # 1. Create Checkpoint
    with patch.object(CRUDRepository, "create_migration_checkpoint", AsyncMock(return_value=mock_cp)):
        checkpoint = await create_git_checkpoint(temp_git_repo, run_id, project_id, db)
        assert checkpoint.commit_sha is not None

    # 2. Modify file in the repo
    test_file = os.path.join(temp_git_repo, "test.txt")
    with open(test_file, "w") as f:
        f.write("destructive modified content")

    # 3. Trigger Rollback
    with patch.object(CRUDRepository, "get_migration_checkpoints", AsyncMock(return_value=[mock_cp])), \
         patch.object(CRUDRepository, "update_checkpoint_rollback_status", AsyncMock()), \
         patch.object(CRUDRepository, "get_migration_run", AsyncMock(return_value=mock_run)):
        res = await rollback_git_checkpoint(run_id, db)
        assert res["status"] == "SUCCESS"

    # 4. Verify file was reverted to baseline
    with open(test_file, "r") as f:
        assert f.read() == "initial baseline content"


from fastapi import HTTPException
from app.api.recipes import (
    _score_recipe,
    _resolve_execution_order,
    _is_version_compatible,
    RecommendRequest,
)

def test_recipe_scoring_determinism():
    """Verify that scoring is completely deterministic and yields reasons list."""
    req = RecommendRequest(
        project_id="test-proj",
        workspace_path="/tmp/test",
        languages=["python"],
        frameworks=["django"],
        detected_deps=["django"],
        has_tests=True,
        has_ci=False
    )
    
    recipe = {
        "id": "test-recipe",
        "language": "python",
        "category": "upgrade",
        "complexity": "medium",
        "tags": ["django", "ci"]
    }
    
    score1, reasons1 = _score_recipe(recipe, req)
    score2, reasons2 = _score_recipe(recipe, req)
    
    assert score1 == score2
    assert reasons1 == reasons2
    assert score1 > 0
    assert any("language" in r.lower() for r in reasons1)


def test_version_compatibility_gates():
    """Verify that version limits prevent inapplicable recipe execution."""
    recipe = {
        "id": "java17-recipe",
        "min_version": "17",
        "max_version": "21"
    }
    
    assert _is_version_compatible(recipe, "8", "11") is False
    assert _is_version_compatible(recipe, "11", "17") is True
    assert _is_version_compatible(recipe, "17", "21") is True


def test_transitive_dependency_resolution():
    """Verify that topological sort resolves transitive dependencies in correct sequence."""
    import app.api.recipes
    mock_catalog = {
        "recipe-A": {"id": "recipe-A", "requires": ["recipe-B"]},
        "recipe-B": {"id": "recipe-B", "requires": ["recipe-C"]},
        "recipe-C": {"id": "recipe-C", "requires": []}
    }
    
    original_catalog = app.api.recipes._CATALOG_BY_ID
    app.api.recipes._CATALOG_BY_ID = mock_catalog
    try:
        resolved = _resolve_execution_order(["recipe-A"])
        assert resolved == ["recipe-C", "recipe-B", "recipe-A"]
    finally:
        app.api.recipes._CATALOG_BY_ID = original_catalog


def test_cycle_detection_blocks_execution():
    """Verify that dependency loop returns RECIPE_DEPENDENCY_CYCLE."""
    import app.api.recipes
    mock_catalog = {
        "recipe-A": {"id": "recipe-A", "requires": ["recipe-B"]},
        "recipe-B": {"id": "recipe-B", "requires": ["recipe-C"]},
        "recipe-C": {"id": "recipe-C", "requires": ["recipe-A"]}
    }
    
    original_catalog = app.api.recipes._CATALOG_BY_ID
    app.api.recipes._CATALOG_BY_ID = mock_catalog
    try:
        with pytest.raises(HTTPException) as exc_info:
            _resolve_execution_order(["recipe-A"])
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["type"] == "RECIPE_DEPENDENCY_CYCLE"
        assert "recipe-A" in exc_info.value.detail["recipes"]
    finally:
        app.api.recipes._CATALOG_BY_ID = original_catalog


# ── Phase 6 Sandbox Execution & Worker Isolation Tests ─────────────────────────
from app.core.git_safety import run_secured_command, validate_workspace_path, SubprocessSecurityError

def test_workspace_path_traversal_gates(tmp_path):
    """Verify that path traversal attempts outside workspace are blocked."""
    workspace_root = str(tmp_path / "sandbox")
    os.makedirs(workspace_root, exist_ok=True)
    
    # Inside boundary should succeed
    inside = str(tmp_path / "sandbox" / "src")
    os.makedirs(inside, exist_ok=True)
    assert validate_workspace_path(inside, workspace_root) == os.path.abspath(inside)
    
    # Outside boundary should throw SubprocessSecurityError
    outside = str(tmp_path / "outside_dir")
    os.makedirs(outside, exist_ok=True)
    with pytest.raises(SubprocessSecurityError):
        validate_workspace_path(outside, workspace_root)


def test_env_secrets_stripping(tmp_path):
    """Verify that run_secured_command filters out DB/Redis credentials/secrets."""
    workspace_root = str(tmp_path)
    os.environ["DATABASE_PASSWORD"] = "extremelysecretpass"
    os.environ["REDIS_URL"] = "redis://somehost:6379"
    os.environ["PATH"] = "/usr/bin"
    
    # Import run_secured_command to verify it cleans env
    import subprocess
    import sys
    
    cmd = [sys.executable, "-c", "import os; print(list(os.environ.keys()))"]
    res = run_secured_command(cmd, workspace_root, timeout_seconds=10)
    
    # Stderr/stdout should show stripped keys
    stdout_keys = res["stdout"]
    assert "DATABASE_PASSWORD" not in stdout_keys
    assert "REDIS_URL" not in stdout_keys


