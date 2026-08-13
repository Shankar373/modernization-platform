"""Git repository safety verification and checkpoint recovery manager."""
import os
import git
from datetime import datetime
from app.db.crud import CRUDRepository
from app.db.models import DBMigrationCheckpoint


def verify_workspace_is_git(workspace_path: str) -> bool:
    """Check if the given workspace path is a valid Git repository."""
    try:
        git.Repo(workspace_path)
        return True
    except (git.exc.InvalidGitRepositoryError, git.exc.NoSuchPathError):
        return False


def get_repo_info(workspace_path: str) -> dict:
    """Retrieve current branch, HEAD SHA, and dirty status of the workspace."""
    try:
        repo = git.Repo(workspace_path)
        # Determine current branch safely
        try:
            branch = repo.active_branch.name
        except TypeError:
            branch = "DETACHED_HEAD"
            
        head_sha = repo.head.commit.hexsha
        is_dirty = repo.is_dirty(untracked_files=True)
        status_text = repo.git.status()
        
        return {
            "branch": branch,
            "head_sha": head_sha,
            "is_dirty": is_dirty,
            "status_text": status_text,
        }
    except Exception as e:
        return {
            "branch": None,
            "head_sha": None,
            "is_dirty": True,
            "status_text": f"Error loading repository info: {e}",
        }


async def create_git_checkpoint(workspace_path: str, run_id: str, project_id: str, db) -> DBMigrationCheckpoint:
    """
    Ensures workspace is a Git repository, verifies cleanliness, commits/references
    a baseline checkpoint immediately before transformation, and persists to DB.
    """
    repo_path = os.path.abspath(workspace_path)
    
    # 1. Initialize Git repository if it doesn't exist (e.g. for ZIP uploads)
    if not verify_workspace_is_git(repo_path):
        try:
            repo = git.Repo.init(repo_path)
            # Configure dummy local user details for this commit
            repo.config_writer().set_value("user", "name", "SystemaOps Autopilot").release()
            repo.config_writer().set_value("user", "email", "autopilot@systemaops.com").release()
            # Commit baseline
            repo.git.add(A=True)
            repo.git.commit(m="SystemaOps Baseline Checkpoint")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize temporary Git repository in workspace: {e}")

    repo = git.Repo(repo_path)
    info = get_repo_info(repo_path)

    # 2. Check for dirty working trees (prevent modernization if user has uncommitted changes)
    # Note: if it's our own baseline commit, it won't be dirty.
    if info["is_dirty"]:
        # Stage and commit any untracked or unstaged modifications as a pre-modernization auto-commit
        # to ensure they are not lost!
        try:
            repo.git.add(A=True)
            repo.git.commit(m="Pre-modernization user checkpoint")
            # Refresh info
            info = get_repo_info(repo_path)
        except Exception as e:
            raise RuntimeError(f"Workspace contains uncommitted changes and auto-commit failed: {e}")

    # 3. Save checkpoint to database
    db_cp = await CRUDRepository.create_migration_checkpoint(
        db=db,
        project_id=project_id,
        run_id=run_id,
        commit_sha=info["head_sha"],
        description="Pre-transformation checkpoint",
        branch=info["branch"],
        repository_path=repo_path,
        repository_status=info["status_text"],
        rollback_status="AVAILABLE",
    )
    return db_cp


async def rollback_git_checkpoint(run_id: str, db) -> dict:
    """
    Identifies the most recent pre-transformation checkpoint for a run,
    checks repository safety guidelines, and rolls back the workspace modifications.
    """
    checkpoints = await CRUDRepository.get_migration_checkpoints(db, run_id)
    if not checkpoints:
        return {"status": "BLOCKED", "message": "No checkpoint found for migration run."}

    checkpoint = checkpoints[0]
    repo_path = checkpoint.repository_path

    if not verify_workspace_is_git(repo_path):
        await CRUDRepository.update_checkpoint_rollback_status(
            db, checkpoint.checkpoint_id, "FAILED", "Workspace is no longer a valid Git repository."
        )
        return {"status": "FAILED", "message": "Workspace is no longer a valid Git repository."}

    try:
        repo = git.Repo(repo_path)
        # Update status
        await CRUDRepository.update_checkpoint_rollback_status(
            db, checkpoint.checkpoint_id, "IN_PROGRESS"
        )

        # Safety Check: check if the commit SHA exists in the history
        try:
            repo.commit(checkpoint.commit_sha)
        except Exception:
            await CRUDRepository.update_checkpoint_rollback_status(
                db, checkpoint.checkpoint_id, "FAILED", f"Checkpoint commit SHA {checkpoint.commit_sha} not found in Git repository."
            )
            return {"status": "FAILED", "message": f"Checkpoint commit SHA {checkpoint.commit_sha} not found in history."}

        # Perform clean rollback to target commit SHA
        repo.git.reset("--hard", checkpoint.commit_sha)
        repo.git.clean("-fd")

        # Update status on success
        await CRUDRepository.update_checkpoint_rollback_status(
            db, checkpoint.checkpoint_id, "SUCCESS"
        )
        return {"status": "SUCCESS", "message": f"Rollback to checkpoint {checkpoint.commit_sha} succeeded."}

    except Exception as e:
        trace = traceback.format_exc() if "traceback" in globals() else str(e)
        await CRUDRepository.update_checkpoint_rollback_status(
            db, checkpoint.checkpoint_id, "FAILED", f"Git reset error: {e}"
        )
        return {"status": "FAILED", "message": f"Git reset failed: {e}"}
