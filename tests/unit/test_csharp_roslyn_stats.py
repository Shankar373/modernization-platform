"""Regression tests: CSharpRoslynAdapter statistics must reflect actual validation results,
not hardcoded build/test success. Covers pass, fail, and skipped (validation not executed)."""
from pathlib import Path
from unittest.mock import patch
import pytest

from app.adapters.base import adapter_registry
from app.core.domain.models import MigrationProfile
from app.core.orchestration.orchestrator import MigrationOrchestrator

BALANCED_CS = """using System;
namespace App
{
    public class Program
    {
        public static void Main() {}
    }
}
"""

UNBALANCED_CS = """using System;
namespace App
{
    public class Program
    {
        public static void Main() { {
    }
}
"""

def _build_plan(ws_path: str):
    from app.core.domain.models import MigrationPlan, PlanStep, MigrationTarget
    from app.core.orchestration.orchestrator import MigrationOrchestrator
    
    step = PlanStep(
        step_id="step-1",
        order=1,
        name="C# Upgrade",
        description="Upgrade C# target framework",
        adapter="csharp",
        capability="csharp-roslyn-ast"
    )
    plan = MigrationPlan(
        plan_id="plan-123",
        project_id="proj-123",
        profile=MigrationProfile.CONSERVATIVE,
        targets=[MigrationTarget(language="csharp", target_version="net8.0")],
        steps=[step],
    )
    orchestrator = MigrationOrchestrator()
    return orchestrator, plan


@pytest.fixture(autouse=True)
def mock_dotnet_toolchain():
    import subprocess
    real_run = subprocess.run

    def conditional_run(cmd, *args, **kwargs):
        if not isinstance(cmd, list) or not cmd:
            return real_run(cmd, *args, **kwargs)
        
        cmd_str = " ".join(str(c) for c in cmd)
        
        # Always let RoslynTool.dll run for real AST work
        if "RoslynTool.dll" in cmd_str:
            return real_run(cmd, *args, **kwargs)
        
        # Only intercept dotnet subcommands
        if str(cmd[0]) != "dotnet" or len(cmd) < 2:
            return real_run(cmd, *args, **kwargs)
        
        subcommand = str(cmd[1])  # "build", "test", "format", etc.
        proj_arg = " ".join(str(c) for c in cmd[2:])  # the project/path argument(s)
        
        if "fail_build.csproj" in proj_arg:
            # build fails, test never runs
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=1,
                stdout="Build failed. Error CS0103: The name 'xyz' does not exist in the current context.",
                stderr=""
            )
        elif "fail_test.csproj" in proj_arg:
            if subcommand == "test":
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=1,
                    stdout="Passed!  - Failed:     2, Passed:     1, Skipped:     0, Total:     3",
                    stderr=""
                )
            else:
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0, stdout="Build succeeded.", stderr=""
                )
        else:
            if subcommand == "test":
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=0,
                    stdout="Passed!  - Failed:     0, Passed:     3, Skipped:     0, Total:     3",
                    stderr=""
                )
            else:
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0, stdout="Build succeeded.", stderr=""
                )

    with patch("shutil.which", return_value="mock_dotnet"), \
         patch("subprocess.run", side_effect=conditional_run):
        yield


def test_csharp_stats_skipped_when_validation_not_run(tmp_path: Path):
    (tmp_path / "Program.cs").write_text(BALANCED_CS, encoding="utf-8")
    _, plan = _build_plan(str(tmp_path))

    adapter = adapter_registry.get_by_language("csharp")
    result = adapter.migrate(str(tmp_path), plan)

    assert result.status.value == "SUCCESS"
    assert result.statistics.build_passed is None
    assert result.statistics.tests_passed == 0
    assert result.statistics.tests_failed == 0
    assert result.statistics.tests_total == 0


def test_csharp_stats_pass_when_validation_passes(tmp_path: Path):
    (tmp_path / "Program.cs").write_text(BALANCED_CS, encoding="utf-8")
    (tmp_path / "test.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk"></Project>', encoding="utf-8")
    orchestrator, plan = _build_plan(str(tmp_path))

    result = orchestrator.migrate(str(tmp_path), plan)

    assert result.statistics.build_passed is True
    assert result.statistics.tests_passed is True
    assert result.statistics.tests_total == 3
    assert result.statistics.tests_failed == 0


def test_csharp_stats_fail_when_validation_fails(tmp_path: Path):
    (tmp_path / "Program.cs").write_text(UNBALANCED_CS, encoding="utf-8")
    orchestrator, plan = _build_plan(str(tmp_path))

    result = orchestrator.migrate(str(tmp_path), plan)

    assert result.statistics.build_passed is False
    assert result.statistics.tests_passed is False


def test_csharp_stats_fail_when_build_fails(tmp_path: Path):
    (tmp_path / "Program.cs").write_text(BALANCED_CS, encoding="utf-8")
    (tmp_path / "fail_build.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk"></Project>', encoding="utf-8")
    orchestrator, plan = _build_plan(str(tmp_path))

    result = orchestrator.migrate(str(tmp_path), plan)

    assert result.statistics.build_passed is False
    assert result.statistics.tests_passed is False


def test_csharp_stats_fail_when_tests_fail(tmp_path: Path):
    (tmp_path / "Program.cs").write_text(BALANCED_CS, encoding="utf-8")
    (tmp_path / "fail_test.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk"></Project>', encoding="utf-8")
    orchestrator, plan = _build_plan(str(tmp_path))

    result = orchestrator.migrate(str(tmp_path), plan)

    assert result.statistics.build_passed is True
    assert result.statistics.tests_passed is False
    assert result.statistics.tests_total == 3
    assert result.statistics.tests_failed == 2
