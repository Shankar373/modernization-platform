"""Secure repository ingestion — ZIP upload and Git URL."""
from __future__ import annotations

import os
import shutil
import uuid
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import git

from app.config import settings


_ALLOWED_GIT_SCHEMES = {"https", "http"}
_BLOCKED_HOSTS = {"169.254.169.254", "localhost", "127.0.0.1", "0.0.0.0", "::1"}


class SecurityError(Exception):
    """Raised when a security violation is detected during ingestion."""


class IngestionService:
    """
    Secure repository ingestion.

    Protects against:
    - Path traversal in ZIP archives
    - Archive bomb (zip bomb) attacks
    - SSRF via malicious Git URLs
    - Oversized uploads
    """

    def __init__(self):
        self.workspace_base = Path(settings.workspace_base_path)
        self.workspace_base.mkdir(parents=True, exist_ok=True)

    def create_workspace(self, project_name: str) -> tuple[str, str]:
        """Create an isolated workspace directory for a migration job."""
        project_id = str(uuid.uuid4())
        ws_path = self.workspace_base / project_id
        ws_path.mkdir(parents=True, exist_ok=True)
        return project_id, str(ws_path)

    def ingest_zip(self, zip_bytes: bytes, workspace_path: str) -> None:
        """
        Extract a ZIP archive into the workspace with security checks.

        Raises SecurityError on:
        - Path traversal attempts
        - Archive bomb (ratio > MAX_ARCHIVE_RATIO)
        - Files exceeding size limit
        """
        max_size = settings.max_upload_size_mb * 1024 * 1024
        max_ratio = settings.max_archive_ratio

        if len(zip_bytes) > max_size:
            raise SecurityError(f"Upload exceeds maximum size of {settings.max_upload_size_mb}MB")

        ws = Path(workspace_path)
        total_extracted = 0

        # Write zip to temp file for inspection
        tmp_zip = ws / "_upload.zip"
        tmp_zip.write_bytes(zip_bytes)

        try:
            with zipfile.ZipFile(str(tmp_zip), "r") as zf:
                for info in zf.infolist():
                    # Reject path traversal
                    member_path = os.path.normpath(info.filename)
                    if member_path.startswith("..") or os.path.isabs(member_path):
                        raise SecurityError(f"Path traversal attempt detected: {info.filename}")

                    # Check individual file size
                    if info.file_size > max_size:
                        raise SecurityError(f"File too large inside archive: {info.filename}")

                    # Archive bomb check
                    if info.compress_size > 0:
                        ratio = info.file_size / info.compress_size
                        if ratio > max_ratio:
                            raise SecurityError(
                                f"Potential archive bomb detected in {info.filename} "
                                f"(compression ratio: {ratio:.1f}x)"
                            )

                    total_extracted += info.file_size
                    if total_extracted > max_size * max_ratio:
                        raise SecurityError("Archive bomb detected — total extracted size too large")

                zf.extractall(str(ws))
            
            # Post-extract cleanup: flatten if zip had a single root directory
            self._flatten_single_directory(ws)
        finally:
            tmp_zip.unlink(missing_ok=True)

    def _flatten_single_directory(self, ws: Path) -> None:
        """If workspace has exactly one directory and no other files, move its contents to the root."""
        entries = list(ws.iterdir())
        # Filter out hidden files and the temporary upload zip
        entries = [e for e in entries if not e.name.startswith(".") and e.name != "_upload.zip"]
        
        if len(entries) == 1 and entries[0].is_dir():
            single_dir = entries[0]
            # Move all contents of the single directory to the parent workspace root
            for item in single_dir.iterdir():
                # Avoid moving back into itself
                shutil.move(str(item), str(ws))
            # Delete the now-empty subdirectory
            shutil.rmtree(str(single_dir), ignore_errors=True)

    def ingest_git(self, git_url: str, workspace_path: str, branch: str = "main") -> None:
        """
        Clone a Git repository into the workspace with SSRF protection.

        Raises SecurityError on suspicious URLs.
        """
        self._validate_git_url(git_url)
        ws = Path(workspace_path)
        try:
            git.Repo.clone_from(git_url, str(ws), branch=branch, depth=1)
        except git.exc.GitCommandError:
            # Try without branch specification
            try:
                git.Repo.clone_from(git_url, str(ws), depth=1)
            except git.exc.GitCommandError as e:
                raise ValueError(f"Failed to clone repository: {e}")

    def _validate_git_url(self, url: str) -> None:
        """Validate Git URL to prevent SSRF attacks."""
        try:
            parsed = urlparse(url)
        except Exception:
            raise SecurityError("Invalid Git URL")

        if parsed.scheme not in _ALLOWED_GIT_SCHEMES:
            raise SecurityError(f"Unsupported Git URL scheme: {parsed.scheme}. Only https/http allowed.")

        hostname = parsed.hostname or ""
        if hostname in _BLOCKED_HOSTS:
            raise SecurityError(f"Blocked host in Git URL: {hostname}")

        # Block private IP ranges
        import ipaddress
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                raise SecurityError(f"Private/loopback IP in Git URL: {hostname}")
        except ValueError:
            pass  # Not an IP — hostname is fine

    def cleanup_workspace(self, workspace_path: str) -> None:
        """Remove a workspace after use."""
        ws = Path(workspace_path)
        if ws.exists() and str(self.workspace_base) in str(ws):
            shutil.rmtree(str(ws), ignore_errors=True)
