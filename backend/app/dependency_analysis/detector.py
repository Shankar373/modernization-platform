"""
Dependency File Detector

Discovers all dependency-definition files in a workspace.
Extensible: add new ecosystems by extending _ECOSYSTEM_FILES.
Lockfiles are flagged and never directly modified.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from app.dependency_analysis.models import DependencyEcosystem, DependencyFile


# ── Ecosystem file signatures ────────────────────────────────────────────────
# Each entry: (filename_or_glob, ecosystem, is_lockfile)
_ECOSYSTEM_FILES: List[tuple] = [
    # Python
    ("requirements.txt",     DependencyEcosystem.PYTHON, False),
    ("requirements-dev.txt", DependencyEcosystem.PYTHON, False),
    ("requirements-test.txt",DependencyEcosystem.PYTHON, False),
    ("requirements-prod.txt",DependencyEcosystem.PYTHON, False),
    ("pyproject.toml",       DependencyEcosystem.PYTHON, False),
    ("setup.py",             DependencyEcosystem.PYTHON, False),
    ("setup.cfg",            DependencyEcosystem.PYTHON, False),
    ("Pipfile",              DependencyEcosystem.PYTHON, False),
    ("Pipfile.lock",         DependencyEcosystem.PYTHON, True),
    ("poetry.lock",          DependencyEcosystem.PYTHON, True),

    # Node / JavaScript / TypeScript
    ("package.json",         DependencyEcosystem.NODE,   False),
    ("package-lock.json",    DependencyEcosystem.NODE,   True),
    ("yarn.lock",            DependencyEcosystem.NODE,   True),
    ("pnpm-lock.yaml",       DependencyEcosystem.NODE,   True),

    # Java
    ("pom.xml",              DependencyEcosystem.JAVA,   False),
    ("build.gradle",         DependencyEcosystem.JAVA,   False),
    ("build.gradle.kts",     DependencyEcosystem.JAVA,   False),

    # .NET
    ("packages.config",      DependencyEcosystem.DOTNET, False),
]

# Glob patterns for ecosystem files (e.g. *.csproj)
_GLOB_PATTERNS: List[tuple] = [
    ("*.csproj",             DependencyEcosystem.DOTNET, False),
]

# Directories that must be ignored during discovery
_IGNORE_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__",
    ".idea", "target", "build", "dist", "site-packages", "vendor",
    ".pytest_cache", ".next", ".tox",
}


class DependencyFileDetector:
    """
    Walks the workspace and returns all dependency-definition files
    grouped by ecosystem.  Lockfiles are flagged as is_lockfile=True.
    """

    def detect(self, workspace_path: str) -> List[DependencyFile]:
        ws = Path(workspace_path)
        if not ws.exists():
            return []

        found: List[DependencyFile] = []
        seen: set[str] = set()

        for rel_path, ecosystem, is_lock in _ECOSYSTEM_FILES:
            for match in ws.rglob(rel_path):
                if self._is_ignored(match):
                    continue
                key = str(match.resolve())
                if key in seen:
                    continue
                seen.add(key)
                found.append(DependencyFile(
                    path=str(match.relative_to(ws)).replace("\\", "/"),
                    ecosystem=ecosystem,
                    is_lockfile=is_lock,
                ))

        for pattern, ecosystem, is_lock in _GLOB_PATTERNS:
            for match in ws.rglob(pattern):
                if self._is_ignored(match):
                    continue
                key = str(match.resolve())
                if key in seen:
                    continue
                seen.add(key)
                found.append(DependencyFile(
                    path=str(match.relative_to(ws)).replace("\\", "/"),
                    ecosystem=ecosystem,
                    is_lockfile=is_lock,
                ))

        return found

    @staticmethod
    def _is_ignored(path: Path) -> bool:
        for part in path.parts:
            pl = part.lower()
            if pl in _IGNORE_DIRS:
                return True
            if pl.startswith(".venv") or pl == "venv" or "site-packages" in pl:
                return True
        return False

