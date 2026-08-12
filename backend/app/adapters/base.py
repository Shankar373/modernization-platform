from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

def is_ignored_path(path: Path) -> bool:
    """Check if a path contains any standard ignored directory names or virtualenvs."""
    ignore_dirs = {".git", "node_modules", ".venv", "venv", "__pycache__", ".idea", "target", "build", "dist", "site-packages", "vendor", ".pytest_cache", ".next", ".ruff_cache", ".mypy_cache"}
    for p in path.parts:
        pl = p.lower()
        if pl in ignore_dirs or pl.startswith(".venv") or "venv" in pl or "site-packages" in pl:
            return True
    return False

from app.core.domain.models import (
    MigrationCapability,
    MigrationPlan,
    MigrationProfile,
    MigrationResult,
    TechnologyProfile,
)


class AnalysisResult:
    """Result of adapter-level analysis."""
    def __init__(self, applicable: bool, notes: str = "", metadata: dict = None):
        self.applicable = applicable
        self.notes = notes
        self.metadata = metadata or {}


class DryRunResult:
    """Result of adapter-level dry run."""
    def __init__(
        self,
        success: bool,
        files_would_change: int = 0,
        preview_diffs: list = None,
        warnings: list = None,
        notes: str = "",
    ):
        self.success = success
        self.files_would_change = files_would_change
        self.preview_diffs = preview_diffs or []
        self.warnings = warnings or []
        self.notes = notes


class ValidationResult:
    """Result of post-migration validation."""
    def __init__(
        self,
        build_passed: bool = False,
        tests_passed: bool = False,
        tests_total: int = 0,
        tests_failed: int = 0,
        security_passed: bool = True,
        warnings: list = None,
        errors: list = None,
        raw_output: str = "",
    ):
        self.build_passed = build_passed
        self.tests_passed = tests_passed
        self.tests_total = tests_total
        self.tests_failed = tests_failed
        self.security_passed = security_passed
        self.warnings = warnings or []
        self.errors = errors or []
        self.raw_output = raw_output


class MigrationAdapter(ABC):
    """
    Abstract base class for all language migration adapters.

    Every adapter (Java/OpenRewrite, Python/Ruff, future connectors) must
    implement this interface. The core orchestrator never contains
    language-specific logic — it delegates entirely to adapters via this contract.
    """

    @property
    @abstractmethod
    def language(self) -> str:
        """Language this adapter handles (e.g., 'java', 'python')."""
        ...

    @property
    @abstractmethod
    def provider(self) -> str:
        """Migration tool provider (e.g., 'openrewrite', 'ruff')."""
        ...

    @abstractmethod
    def detect(self, workspace_path: str) -> bool:
        """
        Return True if this adapter is applicable to the repository at workspace_path.
        Must NOT modify any files.
        """
        ...

    @abstractmethod
    def analyze(self, profile: TechnologyProfile) -> AnalysisResult:
        """
        Analyze the technology profile for adapter-specific insights.
        Must NOT modify any files.
        """
        ...

    @abstractmethod
    def get_capabilities(self) -> List[MigrationCapability]:
        """
        Return the list of migration capabilities this adapter supports.
        Status must reflect actual availability, never fake AVAILABLE.
        """
        ...

    @abstractmethod
    def create_plan(
        self,
        workspace_path: str,
        profile: TechnologyProfile,
        target_version: str,
        migration_profile: MigrationProfile = MigrationProfile.CONSERVATIVE,
    ) -> MigrationPlan:
        """
        Create a migration plan for this repository.
        Must NOT modify any files.
        """
        ...

    @abstractmethod
    def dry_run(self, workspace_path: str, plan: MigrationPlan) -> DryRunResult:
        """
        Execute a dry run — show what WOULD change without modifying files.
        """
        ...

    @abstractmethod
    def migrate(self, workspace_path: str, plan: MigrationPlan) -> MigrationResult:
        """
        Execute the actual migration. Only called after user approval.
        Must produce real diffs — never fabricate changes.
        """
        ...

    @abstractmethod
    def validate(self, workspace_path: str, result: MigrationResult) -> ValidationResult:
        """
        Validate the migrated repository (build, test, static analysis).
        """
        ...

    @abstractmethod
    def generate_report(self, result: MigrationResult, validation: ValidationResult) -> dict:
        """
        Generate a structured migration report.
        Must not report SUCCESS unless validation actually passed.
        """
        ...
