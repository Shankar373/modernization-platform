"""Unit tests for Git safety validation, checkpoints, and rollback recovery."""
import pytest
import os
import shutil
import tempfile
import git
from unittest.mock import MagicMock, AsyncMock

from app.core.git_safety import (
    verify_workspace_is_git,
    get_repo_info,
    create_git_checkpoint,
    rollback_git_checkpoint,
)
from app.db.models import DBMigrationCheckpoint


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


def test_verify_git_repo(temp_git_repo):
    """Verify Git repository detection."""
    assert verify_workspace_is_git(temp_git_repo) is True
    assert verify_workspace_is_git("/nonexistent/path/safety") is False


def test_get_repo_info(temp_git_repo):
    """Verify repo details retrieval."""
    info = get_repo_info(temp_git_repo)
    assert info["branch"] is not None
    assert info["head_sha"] is not None
    assert info["is_dirty"] is False


@pytest.mark.asyncio
async def test_checkpoint_creation_and_rollback(temp_git_repo):
    """Verify that checkpoint is created and rollback reverts modifications."""
    db = MagicMock()
    run_id = "test-run-id"
    project_id = "test-project-id"

    # Mock DB checkpoint row
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

    # Patch DB CRUD calls
    from app.db.crud import CRUDRepository
    CRUDRepository.create_migration_checkpoint = AsyncMock(return_value=mock_cp)
    CRUDRepository.get_migration_checkpoints = AsyncMock(return_value=[mock_cp])
    CRUDRepository.update_checkpoint_rollback_status = AsyncMock()

    # 1. Create Checkpoint
    checkpoint = await create_git_checkpoint(temp_git_repo, run_id, project_id, db)
    assert checkpoint.commit_sha is not None

    # 2. Modify files in the repo (simulate transformation/destructiveness)
    test_file = os.path.join(temp_git_repo, "test.txt")
    with open(test_file, "w") as f:
        f.write("destructive modified content")
    
    # Verify file is changed
    with open(test_file, "r") as f:
        assert f.read() == "destructive modified content"

    # 3. Trigger Rollback
    res = await rollback_git_checkpoint(run_id, db)
    assert res["status"] == "SUCCESS"

    # 4. Verify file was reverted to baseline content
    with open(test_file, "r") as f:
        assert f.read() == "initial baseline content"
