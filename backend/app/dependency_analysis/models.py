"""
Dependency Analysis — Domain Models

Rich, ecosystem-aware dependency domain model with status tracking.
Completely separate from the migration pipeline domain models.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class DependencyStatus(str, Enum):
    UP_TO_DATE        = "UP_TO_DATE"
    UPDATE_AVAILABLE  = "UPDATE_AVAILABLE"
    CONSTRAINT_BLOCKED = "CONSTRAINT_BLOCKED"
    LOOKUP_FAILED     = "LOOKUP_FAILED"
    INVALID_VERSION   = "INVALID_VERSION"


class DependencyEcosystem(str, Enum):
    PYTHON  = "python"
    NODE    = "node"
    JAVA    = "java"
    DOTNET  = "dotnet"
    UNKNOWN = "unknown"


class Dependency(BaseModel):
    """
    Normalized dependency extracted from a dependency-definition file.

    current_version      — the pinned version string as written in the file
    version_constraint   — the full constraint expression (e.g. ">=2.25,<3")
    latest_stable_version — resolved at runtime from the package registry
    status               — result of comparing current vs latest
    """
    name: str
    current_version: Optional[str] = None
    version_constraint: Optional[str] = None
    latest_stable_version: Optional[str] = None
    source_file: str
    ecosystem: DependencyEcosystem
    status: DependencyStatus = DependencyStatus.LOOKUP_FAILED
    update_required: bool = False
    reason: str = ""

    # Optional extras / environment markers preserved verbatim
    extras: Optional[str] = None            # e.g.  "[security]"
    environment_marker: Optional[str] = None  # e.g.  "; python_version >= '3.8'"


class DependencyFile(BaseModel):
    """Metadata about a detected dependency-definition file."""
    path: str                         # relative path inside workspace
    ecosystem: DependencyEcosystem
    is_lockfile: bool = False         # never auto-update lockfiles


class DependencyUpdateAction(BaseModel):
    """A single proposed update for one dependency."""
    dependency_name: str
    source_file: str
    ecosystem: DependencyEcosystem
    current_version: Optional[str]
    proposed_version: str             # always a dynamically resolved real version
    action: str = "UPDATE"            # UPDATE | SKIP | BLOCKED
    reason: str = ""


class ValidationStatus(str, Enum):
    PASSED  = "PASSED"
    FAILED  = "FAILED"
    SKIPPED = "SKIPPED"


class DependencyAnalysisResult(BaseModel):
    """Structured result of the full dependency analysis pipeline."""
    workspace_path: str
    dependency_files: List[DependencyFile] = Field(default_factory=list)
    dependencies: List[Dependency] = Field(default_factory=list)

    # Convenience partitions
    up_to_date: List[str]          = Field(default_factory=list)
    outdated: List[str]            = Field(default_factory=list)
    constraint_blocked: List[str]  = Field(default_factory=list)
    lookup_failed: List[str]       = Field(default_factory=list)

    proposed_updates: List[DependencyUpdateAction] = Field(default_factory=list)
    changed_files: List[str]       = Field(default_factory=list)

    validation_status: ValidationStatus = ValidationStatus.SKIPPED
    validation_errors: List[str]   = Field(default_factory=list)
    warnings: List[str]            = Field(default_factory=list)
