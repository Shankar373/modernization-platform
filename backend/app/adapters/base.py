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

    @property
    def engine(self) -> str:
        """Human-readable transformation engine name (e.g., 'OpenRewrite', 'LibCST + Ruff', 'Roslyn')."""
        return self.provider

    @property
    def required_tools(self) -> List[str]:
        """CLI tool binaries required by this adapter (e.g., ['mvn'], ['ruff'])."""
        return []

    @property
    def roadmap_priority(self) -> int:
        """Priority index according to target roadmap (1..8, 99 for formatters/auxiliary)."""
        return 99

    @property
    def maturity(self) -> str:
        """Adapter execution maturity ('PRODUCTION', 'STABLE', 'EXPERIMENTAL', 'STUB', 'PLANNED')."""
        return "STABLE"

    def check_environment_readiness(self) -> dict:
        """Check if required CLI binaries exist in the system PATH."""
        import shutil
        missing = [tool for tool in self.required_tools if shutil.which(tool) is None]
        return {
            "ready": len(missing) == 0,
            "missing_tools": missing,
            "required_tools": self.required_tools,
            "engine": self.engine,
            "maturity": self.maturity,
        }


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


class AdapterRegistry:
    """
    Centralized registry managing modernization engine adapters,
    roadmap priority ordering, and environment binary readiness checks.
    """

    def __init__(self):
        self._adapters: List[MigrationAdapter] = []

    def register(self, adapter: MigrationAdapter) -> None:
        """Register a new language migration adapter."""
        for idx, existing in enumerate(self._adapters):
            if existing.language.lower() == adapter.language.lower():
                self._adapters[idx] = adapter
                return
        self._adapters.append(adapter)

    def register_all(self, adapters: List[MigrationAdapter]) -> None:
        """Register a list of language migration adapters."""
        for adapter in adapters:
            self.register(adapter)

    def get_by_language(self, language: str) -> Optional[MigrationAdapter]:
        """Find the registered adapter for a given language."""
        if not language:
            return None
        lang_lower = language.lower()
        for adapter in self._adapters:
            if adapter.language.lower() == lang_lower:
                return adapter
        return None

    def get_by_engine(self, engine_name: str) -> Optional[MigrationAdapter]:
        """Find adapter matching engine name (case-insensitive substring or exact)."""
        if not engine_name:
            return None
        eng_lower = engine_name.lower()
        for adapter in self._adapters:
            if eng_lower in adapter.engine.lower():
                return adapter
        return None

    def get_all(self) -> List[MigrationAdapter]:
        """Return all registered adapters."""
        return list(self._adapters)

    def get_roadmap_status(self) -> List[dict]:
        """
        Return all registered adapters sorted by roadmap priority (1..8).
        """
        sorted_adapters = sorted(self._adapters, key=lambda a: (a.roadmap_priority, a.language))
        return [
            {
                "language": a.language,
                "provider": a.provider,
                "engine": a.engine,
                "roadmap_priority": a.roadmap_priority,
                "maturity": a.maturity,
                "required_tools": a.required_tools,
            }
            for a in sorted_adapters
        ]

    def check_all_readiness(self) -> dict:
        """Check system tool readiness across all registered adapters."""
        return {
            adapter.language: adapter.check_environment_readiness()
            for adapter in self._adapters
        }


# Global singleton adapter registry
adapter_registry = AdapterRegistry()

