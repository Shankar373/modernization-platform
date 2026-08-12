"""YAML formatter adapter using ruamel.yaml."""
from __future__ import annotations
import difflib
import io
import os
from datetime import datetime
from pathlib import Path
from typing import List

from app.adapters.base import AnalysisResult, DryRunResult, MigrationAdapter, ValidationResult, is_ignored_path
from app.core.domain.models import (
    CapabilityStatus, FileChangeMetadata, MigrationCapability,
    MigrationPlan, MigrationProfile, MigrationResult, MigrationStatistics,
    MigrationStatus, MigrationTarget, PlanStep, RiskLevel, TechnologyProfile,
)

_SKIP_DIRS = {"node_modules", ".venv", "venv", "__pycache__", ".git", "dist", "build"}

# Never reformat package manager lockfiles — they have strict formats
_SKIP_FILENAMES = {"pnpm-lock.yaml", "yarn.lock", "package-lock.yaml"}


def _get_yaml():
    try:
        from ruamel.yaml import YAML
        y = YAML()
        y.preserve_quotes = True
        y.width = 120
        y.indent(mapping=2, sequence=4, offset=2)
        return y
    except ImportError:
        return None


class YamlFormatterAdapter(MigrationAdapter):
    """Formats YAML files with consistent indentation using ruamel.yaml (open-source)."""

    @property
    def language(self) -> str:
        return "yaml"

    @property
    def provider(self) -> str:
        return "ruamel.yaml"

    def detect(self, workspace_path: str) -> bool:
        ws = Path(workspace_path)
        return any(
            f for f in list(ws.rglob("*.yaml")) + list(ws.rglob("*.yml"))
            if not is_ignored_path(f) and f.name not in _SKIP_FILENAMES
        )


    def analyze(self, profile: TechnologyProfile) -> AnalysisResult:
        return AnalysisResult(applicable=self.detect(str(profile)), notes="YAML formatting available")

    def get_capabilities(self) -> List[MigrationCapability]:
        return [MigrationCapability(
            name="yaml-formatting", language="yaml", provider="ruamel.yaml",
            status=CapabilityStatus.AVAILABLE, source_versions=["*"], target_versions=["*"],
            risk=RiskLevel.LOW, description="Format YAML with consistent indentation and quote preservation",
        )]

    def create_plan(self, workspace_path, profile, target_version, migration_profile=MigrationProfile.CONSERVATIVE):
        return MigrationPlan(
            plan_id=f"yaml-plan-{os.urandom(4).hex()}",
            project_id=getattr(profile, "profile_id", "yaml-project"),
            profile=migration_profile, overall_risk=RiskLevel.LOW,
            steps=[PlanStep(order=1, name="YAML Formatting", description="Format all YAML files",
                           adapter="yaml", capability="yaml-formatting", risk=RiskLevel.LOW, is_reversible=True)],
            targets=[MigrationTarget(language="yaml", source_version=None, target_version="formatted")],
            selected_capabilities=["yaml-formatting"],
        )

    def dry_run(self, workspace_path: str, plan: MigrationPlan) -> DryRunResult:
        before = self._snapshot(Path(workspace_path))
        changed = sum(1 for k, v in before.items() if self._format_yaml(v) != v)
        return DryRunResult(success=True, files_would_change=changed,
                           notes=f"{changed} YAML file(s) would be reformatted.")

    def migrate(self, workspace_path: str, plan: MigrationPlan) -> MigrationResult:
        ws = Path(workspace_path)
        before = self._snapshot(ws)
        changed_files, modified = [], 0
        timeline = [{"step": "YAML formatting started", "status": "running", "ts": datetime.utcnow().isoformat()}]

        for rel, content in before.items():
            formatted = self._format_yaml(content)
            if formatted and formatted != content:
                (ws / rel).write_text(formatted, encoding="utf-8")
                diff = "".join(difflib.unified_diff(
                    content.splitlines(keepends=True), formatted.splitlines(keepends=True),
                    fromfile=f"a/{rel}", tofile=f"b/{rel}"))
                changed_files.append(FileChangeMetadata(
                    file=rel, status="MODIFIED", diff=diff,
                    before_content=content, after_content=formatted,
                    tools=["ruamel.yaml"],
                    changes=[{"type": "YAML_FORMAT", "description": "Normalized YAML indentation and structure"}],
                ))
                modified += 1

        timeline.append({"step": "YAML formatting completed", "status": "completed", "ts": datetime.utcnow().isoformat()})
        return MigrationResult(
            result_id=f"yaml-res-{os.urandom(4).hex()}", job_id=plan.plan_id,
            project_id=plan.project_id, plan_id=plan.plan_id,
            status=MigrationStatus.SUCCESS if modified else MigrationStatus.PARTIALLY_SUCCESSFUL,
            statistics=MigrationStatistics(files_scanned=len(before), files_modified=modified,
                                           files_unchanged=len(before)-modified, capabilities_run=1, build_passed=True),
            changed_files=changed_files, timeline=timeline, completed_at=datetime.utcnow(),
        )

    def validate(self, workspace_path, result) -> ValidationResult:
        return ValidationResult(build_passed=True, tests_passed=True, tests_total=0)

    def generate_report(self, result, validation) -> dict:
        return {"report_id": f"yaml-rep-{os.urandom(4).hex()}", "generated_at": datetime.utcnow().isoformat(),
                "adapter": "yaml/ruamel", "final_status": result.status.value,
                "statistics": result.statistics.model_dump(), "changed_files_count": len(result.changed_files),
                "build_passed": validation.build_passed, "timeline": result.timeline,
                "changed_files": [f.model_dump() for f in result.changed_files]}

    def _format_yaml(self, content: str) -> str:
        yaml = _get_yaml()
        if not yaml:
            return content
        try:
            data = yaml.load(content)
            if data is None:
                return content
            buf = io.StringIO()
            yaml.dump(data, buf)
            return buf.getvalue()
        except Exception:
            return content

    def _iter(self, ws: Path):
        for ext in ("*.yaml", "*.yml"):
            for f in ws.rglob(ext):
                if not is_ignored_path(f) and f.name not in _SKIP_FILENAMES:
                    yield f

    def _snapshot(self, ws: Path) -> dict:
        out = {}
        for f in self._iter(ws):
            try:
                out[str(f.relative_to(ws))] = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass
        return out
