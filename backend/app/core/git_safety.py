"""Git repository safety verification and checkpoint recovery manager."""
import os
import git
import traceback
from typing import Any, Dict, List, Optional
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
    Ensures workspace is a Git repository, verifies cleanliness, and creates a pre-transformation checkpoint.
    Fails and blocks if the repository contains pre-existing user modifications.
    """
    repo_path = os.path.abspath(workspace_path)
    
    # 1. Initialize Git repository if it doesn't exist (e.g. for ZIP uploads)
    if not verify_workspace_is_git(repo_path):
        try:
            repo = git.Repo.init(repo_path)
            repo.config_writer().set_value("user", "name", "SystemaOps Autopilot").release()
            repo.config_writer().set_value("user", "email", "autopilot@systemaops.com").release()
            repo.git.add(A=True)
            repo.git.commit(m="SystemaOps Baseline Checkpoint")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize temporary Git repository in workspace: {e}")

    repo = git.Repo(repo_path)
    info = get_repo_info(repo_path)

    # 2. Safety Gate: Block execution if pre-existing user changes are found.
    # We do NOT automatically commit user modifications.
    if info["is_dirty"]:
        raise RuntimeError("Workspace is dirty with pre-existing uncommitted user changes. Modernization blocked to protect user changes.")

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
    Safely rolls back the workspace changes back to the pre-transformation checkpoint.
    Blocks the rollback if unexpected user changes are detected after the checkpoint was created.
    """
    checkpoints = await CRUDRepository.get_migration_checkpoints(db, run_id)
    if not checkpoints:
        return {"status": "BLOCKED", "message": "No checkpoint found for migration run."}

    checkpoint = checkpoints[0]
    repo_path = checkpoint.repository_path

    # Verify repository path identity matches
    if not verify_workspace_is_git(repo_path):
        await CRUDRepository.update_checkpoint_rollback_status(
            db, checkpoint.checkpoint_id, "FAILED", "Workspace is no longer a valid Git repository."
        )
        return {"status": "FAILED", "message": "Workspace is no longer a valid Git repository."}

    try:
        repo = git.Repo(repo_path)

        # 1. Safety Check: Verify commit SHA exists in git history
        try:
            repo.commit(checkpoint.commit_sha)
        except Exception:
            await CRUDRepository.update_checkpoint_rollback_status(
                db, checkpoint.checkpoint_id, "FAILED", f"Checkpoint commit SHA {checkpoint.commit_sha} not found in history."
            )
            return {"status": "FAILED", "message": f"Checkpoint commit SHA {checkpoint.commit_sha} not found in history."}

        # 2. Safety Check: Verify branch match if active branch was recorded
        try:
            current_branch = repo.active_branch.name
        except TypeError:
            current_branch = "DETACHED_HEAD"
        if checkpoint.branch and checkpoint.branch != current_branch:
            await CRUDRepository.update_checkpoint_rollback_status(
                db, checkpoint.checkpoint_id, "BLOCKED", f"Branch mismatch: expected {checkpoint.branch}, found {current_branch}"
            )
            return {"status": "BLOCKED", "message": f"Branch mismatch: expected {checkpoint.branch}, found {current_branch}."}

        # 3. Safety Check: Block rollback if unexpected user modifications occurred after checkpoint creation
        # We determine the files currently modified in the workspace
        modified_files = set()
        for diff in repo.index.diff(None):
            modified_files.add(diff.a_path)
        for diff in repo.index.diff("HEAD"):
            modified_files.add(diff.a_path)
        for untracked in repo.untracked_files:
            modified_files.add(untracked)

        # Fetch allowed changed files for this migration run
        db_run = await CRUDRepository.get_migration_run(db, run_id)
        allowed_files = set()
        if db_run and db_run.changed_files:
            for f in db_run.changed_files:
                # Store paths relative to repo root
                path = f.get("file", f.get("file_path"))
                if path:
                    allowed_files.add(path)

        # If any modified file is NOT in the allowed list, block rollback to protect user modifications
        unexpected_files = modified_files - allowed_files
        if unexpected_files:
            # Skip blocking if all changes are inside allowed files or if we want strict blocking
            # Let's filter out hidden cache files or git config files if any
            unexpected_user_files = {f for f in unexpected_files if not f.startswith(".")}
            if unexpected_user_files:
                await CRUDRepository.update_checkpoint_rollback_status(
                    db, checkpoint.checkpoint_id, "BLOCKED", f"Unexpected user changes detected: {unexpected_user_files}"
                )
                return {
                    "status": "BLOCKED",
                    "message": f"Rollback blocked: Unexpected user changes detected in files: {unexpected_user_files}"
                }

        # Update status to IN_PROGRESS
        await CRUDRepository.update_checkpoint_rollback_status(
            db, checkpoint.checkpoint_id, "IN_PROGRESS"
        )

        # 4. Perform rollback safely
        repo.git.reset("--hard", checkpoint.commit_sha)
        repo.git.clean("-fd")

        # Update status on success
        await CRUDRepository.update_checkpoint_rollback_status(
            db, checkpoint.checkpoint_id, "SUCCESS"
        )
        return {"status": "SUCCESS", "message": f"Rollback to checkpoint {checkpoint.commit_sha} succeeded."}

    except Exception as e:
        trace = traceback.format_exc()
        await CRUDRepository.update_checkpoint_rollback_status(
            db, checkpoint.checkpoint_id, "FAILED", f"Git reset error: {e}"
        )
        return {"status": "FAILED", "message": f"Git reset failed: {e}\n{trace}"}


# ── Secure Command Execution (Phase 6 Isolation) ──────────────────────────────
import subprocess
import sys

SAFE_ENV_ALLOWLIST = {
    "PATH", "LANG", "LC_ALL", "SYSTEMROOT", "COMSPEC", "TEMP", "TMP", 
    "PYTHONPATH", "JAVA_HOME", "M2_HOME", "MAVEN_HOME", "NODE_ENV", "USERPROFILE"
}

class SubprocessSecurityError(Exception):
    pass

def validate_workspace_path(path: str, workspace_root: str) -> str:
    abs_root = os.path.abspath(workspace_root)
    abs_path = os.path.abspath(path)
    if not abs_path.startswith(abs_root):
        raise SubprocessSecurityError(f"Path traversal attempt blocked. Path {abs_path} is outside workspace {abs_root}.")
    real_path = os.path.realpath(abs_path)
    real_root = os.path.realpath(abs_root)
    if not real_path.startswith(real_root):
        raise SubprocessSecurityError(f"Symlink boundary bypass attempt blocked. Path {real_path} is outside workspace {real_root}.")
    return abs_path

def run_secured_command(
    args: List[str],
    workspace_root: str,
    cwd: Optional[str] = None,
    timeout_seconds: int = 300,
    additional_env: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    validate_workspace_path(workspace_root, workspace_root)
    if cwd:
        cwd = validate_workspace_path(cwd, workspace_root)
    else:
        cwd = workspace_root

    sanitized_env = {}
    for key, value in os.environ.items():
        if key.upper() in SAFE_ENV_ALLOWLIST:
            sanitized_env[key] = value

    if additional_env:
        for key, value in additional_env.items():
            if key.upper() in SAFE_ENV_ALLOWLIST or not any(sec in key.lower() for sec in ["pass", "secret", "key", "token", "cred"]):
                sanitized_env[key] = value

    try:
        proc = subprocess.run(
            args,
            cwd=cwd,
            env=sanitized_env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=(sys.platform == "win32" and args[0].endswith(".bat"))
        )
        return {
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "timeout_triggered": False
        }
    except subprocess.TimeoutExpired as e:
        return {
            "exit_code": -1,
            "stdout": e.stdout if isinstance(e.stdout, str) else "",
            "stderr": e.stderr if isinstance(e.stderr, str) else "",
            "timeout_triggered": True,
            "error_message": f"Command timed out after {timeout_seconds} seconds."
        }
    except Exception as e:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "timeout_triggered": False,
            "error_message": f"Subprocess execution error: {e}"
        }

