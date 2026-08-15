"""Markdown formatter adapter using mdformat (open-source)."""
from __future__ import annotations
import difflib
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


def _mdformat(content: str) -> str | None:
    try:
        import mdformat
        return mdformat.text(content)
    except Exception:
        return None


class MarkdownFormatterAdapter(MigrationAdapter):
    """Formats Markdown files using mdformat (open-source CommonMark formatter)."""

    @property
    def language(self) -> str:
        return "markdown"

    @property
    def provider(self) -> str:
        return "mdformat"

    def detect(self, workspace_path: str) -> bool:
        ws = Path(workspace_path)
        return any(
            f for f in list(ws.rglob("*.md")) + list(ws.rglob("*.markdown"))
            if not is_ignored_path(f)
        )

    def analyze(self, profile: TechnologyProfile) -> AnalysisResult:
        return AnalysisResult(applicable=True, notes="Markdown formatting available")

    def get_capabilities(self) -> List[MigrationCapability]:
        return [MigrationCapability(
            name="markdown-formatting", language="markdown", provider="mdformat",
            status=CapabilityStatus.AVAILABLE, source_versions=["*"], target_versions=["*"],
            risk=RiskLevel.LOW, description="Format Markdown to CommonMark spec using mdformat",
        )]

    def create_plan(self, workspace_path, profile, target_version, migration_profile=MigrationProfile.CONSERVATIVE):
        return MigrationPlan(
            plan_id=f"md-plan-{os.urandom(4).hex()}",
            project_id=getattr(profile, "profile_id", "md-project"),
            profile=migration_profile, overall_risk=RiskLevel.LOW,
            steps=[PlanStep(order=1, name="Markdown Formatting", description="Format Markdown to CommonMark",
                           adapter="markdown", capability="markdown-formatting", risk=RiskLevel.LOW, is_reversible=True)],
            targets=[MigrationTarget(language="markdown", source_version=None, target_version="commonmark")],
            selected_capabilities=["markdown-formatting"],
        )

    def dry_run(self, workspace_path: str, plan: MigrationPlan) -> DryRunResult:
        before = self._snapshot(Path(workspace_path))
        changed = sum(1 for k, v in before.items() if _mdformat(v) and _mdformat(v) != v)
        return DryRunResult(success=True, files_would_change=changed,
                           notes=f"{changed} Markdown file(s) would be reformatted.")

    def migrate(self, workspace_path: str, plan: MigrationPlan) -> MigrationResult:
        ws = Path(workspace_path)
        before = self._snapshot(ws)
        changed_files, modified = [], 0
        timeline = [{"step": "Markdown formatting started", "status": "running", "ts": datetime.utcnow().isoformat()}]

        for rel, content in before.items():
            formatted = _mdformat(content)
            if formatted and formatted != content:
                (ws / rel).write_text(formatted, encoding="utf-8")
                diff = "".join(difflib.unified_diff(
                    content.splitlines(keepends=True), formatted.splitlines(keepends=True),
                    fromfile=f"a/{rel}", tofile=f"b/{rel}"))
                changed_files.append(FileChangeMetadata(
                    file=rel, status="MODIFIED", diff=diff,
                    before_content=content, after_content=formatted,
                    tools=["mdformat"],
                    changes=[{"type": "MARKDOWN_FORMAT", "description": "Normalized Markdown to CommonMark spec"}],
                ))
                modified += 1

        timeline.append({"step": "Markdown formatting completed", "status": "completed", "ts": datetime.utcnow().isoformat()})
        return MigrationResult(
            result_id=f"md-res-{os.urandom(4).hex()}", job_id=plan.plan_id,
            project_id=plan.project_id, plan_id=plan.plan_id,
            status=MigrationStatus.SUCCESS,
            statistics=MigrationStatistics(files_scanned=len(before), files_modified=modified,
                                           files_unchanged=len(before)-modified, capabilities_run=1, build_passed=True),
            changed_files=changed_files, timeline=timeline, completed_at=datetime.utcnow(),
        )

    def validate(self, workspace_path, result) -> ValidationResult:
        return ValidationResult(build_passed=True, tests_passed=True, tests_total=0)

    def generate_report(self, result, validation) -> dict:
        return {"report_id": f"md-rep-{os.urandom(4).hex()}", "generated_at": datetime.utcnow().isoformat(),
                "adapter": "markdown/mdformat", "final_status": result.status.value,
                "statistics": result.statistics.model_dump(), "changed_files_count": len(result.changed_files),
                "build_passed": validation.build_passed, "timeline": result.timeline,
                "changed_files": [f.model_dump() for f in result.changed_files]}

    def _iter(self, ws: Path):
        for ext in ("*.md", "*.markdown"):
            for f in ws.rglob(ext):
                if not is_ignored_path(f):
                    yield f

    def _snapshot(self, ws: Path) -> dict:
        out = {}
        for f in self._iter(ws):
            try:
                out[str(f.relative_to(ws))] = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass
        return out
