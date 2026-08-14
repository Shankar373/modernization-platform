"""Regression tests: CSharpRoslynAdapter statistics must reflect actual validation results,
not hardcoded build/test success. Covers pass, fail, and skipped (validation not executed)."""
from pathlib import Path

from app.adapters.base import adapter_registry
from app.core.domain.models import MigrationProfile
from app.core.orchestration.orchestrator import MigrationOrchestrator

BALANCED_CS = "namespace Acme.App\n{\npublic class Program {}\n}\n"
UNBALANCED_CS = "namespace Acme.App\n{\npublic class Program {\n"


def _build_plan(workspace_path: str):
    orchestrator = MigrationOrchestrator()
    profile = orchestrator.scan(workspace_path)
    plan = orchestrator.create_plan(workspace_path, profile, "csharp", "net8.0", MigrationProfile.STANDARD)
    assert plan is not None
    return orchestrator, plan


def test_csharp_stats_skipped_when_validation_not_run(tmp_path: Path):
    (tmp_path / "Program.cs").write_text(BALANCED_CS, encoding="utf-8")
    _, plan = _build_plan(str(tmp_path))

    adapter = adapter_registry.get_by_language("csharp")
    result = adapter.migrate(str(tmp_path), plan)

    assert result.status == "SUCCESS"
    assert result.statistics.build_passed is None
    assert result.statistics.tests_passed == 0
    assert result.statistics.tests_failed == 0
    assert result.statistics.tests_total == 0


def test_csharp_stats_pass_when_validation_passes(tmp_path: Path):
    (tmp_path / "Program.cs").write_text(BALANCED_CS, encoding="utf-8")
    orchestrator, plan = _build_plan(str(tmp_path))

    result = orchestrator.migrate(str(tmp_path), plan)

    assert result.statistics.build_passed is True
    assert result.statistics.tests_passed
    assert "unbalanced" not in result.logs["validation"]


def test_csharp_stats_fail_when_validation_fails(tmp_path: Path):
    (tmp_path / "Program.cs").write_text(UNBALANCED_CS, encoding="utf-8")
    orchestrator, plan = _build_plan(str(tmp_path))

    result = orchestrator.migrate(str(tmp_path), plan)

    assert result.statistics.build_passed is False
    assert result.statistics.tests_passed == 0
    assert "unbalanced braces" in result.logs["validation"]