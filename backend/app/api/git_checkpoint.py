"""
Git Checkpoint API

Creates a git checkpoint (commit) in a given workspace directory.

If the workspace has no git repository, one is initialized first.
The checkpoint records all staged/unstaged changes with a descriptive message.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class GitCheckpointRequest(BaseModel):
    workspace_path: str
    project_id: str
    message: str = ""


def _create_checkpoint_sync(workspace_path: str, message: str) -> dict:
    """
    Synchronous git checkpoint implementation (runs in thread pool).
    Uses GitPython to stage all changes and create a commit.
    """
    try:
        import git
    except ImportError:
        raise RuntimeError("GitPython is not installed. Run: pip install gitpython")

    workspace = Path(workspace_path)
    if not workspace.exists():
        raise ValueError(f"Workspace path does not exist: {workspace_path}")

    timestamp = datetime.now().isoformat(timespec="seconds")
    if not message:
        message = f"chore(modernize): pre-migration checkpoint [{timestamp}]"

    # ── Initialize git repo if needed ─────────────────────────────────────────
    try:
        repo = git.Repo(str(workspace), search_parent_directories=False)
        is_new_repo = False
    except git.InvalidGitRepositoryError:
        repo = git.Repo.init(str(workspace))
        is_new_repo = True

        # Write a minimal .gitignore if missing
        gitignore = workspace / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text(
                "__pycache__/\n*.pyc\n*.pyo\n.venv/\nvenv/\n"
                "node_modules/\ndist/\nbuild/\n.env\n*.log\n",
                encoding="utf-8",
            )

    # ── Stage everything ───────────────────────────────────────────────────────
    repo.git.add(A=True)

    # ── Check if there is anything to commit ──────────────────────────────────
    try:
        # On a fresh repo there's no HEAD, index.diff("HEAD") will raise
        diff = repo.index.diff("HEAD")
        staged_count = len(diff)
        untracked = len(repo.untracked_files)
        nothing_to_commit = staged_count == 0 and untracked == 0
    except git.BadName:
        # No HEAD yet — anything staged counts
        nothing_to_commit = False
        staged_count = 0
        untracked = len(repo.untracked_files)

    if nothing_to_commit and not is_new_repo:
        return {
            "status": "nothing_to_commit",
            "message": "No changes detected — working tree is clean.",
            "commit_hash": None,
            "timestamp": timestamp,
            "files_committed": 0,
            "branch": _get_branch(repo),
            "is_new_repo": False,
        }

    # ── Create the commit ──────────────────────────────────────────────────────
    commit = repo.index.commit(message)
    files_committed = len(list(commit.stats.files))

    return {
        "status": "success",
        "commit_hash": commit.hexsha[:12],
        "commit_hash_full": commit.hexsha,
        "commit_message": message,
        "timestamp": datetime.fromtimestamp(commit.committed_date).isoformat(),
        "files_committed": files_committed,
        "branch": _get_branch(repo),
        "is_new_repo": is_new_repo,
        "stats": {
            "insertions": commit.stats.total.get("insertions", 0),
            "deletions": commit.stats.total.get("deletions", 0),
            "files": files_committed,
        },
    }


def _get_branch(repo) -> str:
    try:
        return repo.active_branch.name
    except TypeError:
        return "HEAD (detached)"
    except Exception:
        return "unknown"


@router.post("/git/checkpoint")
async def create_git_checkpoint(request: GitCheckpointRequest):
    """
    Stage all changes in the workspace and create a git commit (checkpoint).

    If the workspace is not a git repository, one is initialized first.
    Returns the commit hash, timestamp, branch name, and file stats.
    """
    try:
        result = await asyncio.to_thread(
            _create_checkpoint_sync,
            request.workspace_path,
            request.message or (
                f"chore(modernize): pre-migration checkpoint — project {request.project_id[:8]}"
            ),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Git checkpoint failed: {e}",
        )


@router.get("/git/checkpoint/download")
async def download_checkpoint_workspace(workspace_path: str, project_id: str):
    """
    Download the current checkpointed workspace as a ZIP file.
    Skips build artifacts, lockfiles, venv, and large metadata directories.
    """
    import io
    import re
    import zipfile
    from fastapi.responses import StreamingResponse

    ws = Path(workspace_path)
    if not ws.exists():
        raise HTTPException(status_code=404, detail="Workspace path does not exist.")

    try:
        # Determine clean project name
        raw_name = ws.name
        clean_root = re.sub(r'[\(\)\s]+', '-', raw_name).strip('-')
        clean_root = re.sub(r'[^a-zA-Z0-9_\-]', '', clean_root) or "workspace"
        filename = f"{clean_root}-checkpoint.zip"

        _SKIP_IN_ZIP = {"__pycache__", "node_modules", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
        _SKIP_IN_ZIP_STARTS = {".git", ".venv", "venv", ".venv-broken"}

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for file_path in sorted(ws.rglob("*")):
                if not file_path.is_file():
                    continue
                rel = file_path.relative_to(ws)
                parts = rel.parts
                # Skip hidden files
                if parts[0].startswith('.'):
                    continue
                # Skip known build/tool directories
                if any(p in _SKIP_IN_ZIP for p in parts):
                    continue
                if any(p.startswith(tuple(_SKIP_IN_ZIP_STARTS)) for p in parts):
                    continue

                arcname = f"{clean_root}/{rel.as_posix()}"
                zf.write(file_path, arcname)
        
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate workspace download: {e}"
        )

