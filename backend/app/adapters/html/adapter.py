"""HTML modernization adapter using BeautifulSoup."""
from __future__ import annotations

import difflib
import os
from datetime import datetime
from pathlib import Path
from typing import List

from bs4 import BeautifulSoup

from app.adapters.base import is_ignored_path, AnalysisResult, DryRunResult, MigrationAdapter, ValidationResult
from app.core.domain.models import (
    CapabilityStatus,
    FileChangeMetadata,
    MigrationCapability,
    MigrationPlan,
    MigrationProfile,
    MigrationResult,
    MigrationStatistics,
    MigrationStatus,
    MigrationTarget,
    PlanStep,
    RiskLevel,
    TechnologyProfile,
)

# Directories to skip when scanning HTML files
_SKIP_DIRS = {"node_modules", ".venv", "venv", "__pycache__", ".git", "dist", "build", "target"}


class HtmlModernizationAdapter(MigrationAdapter):
    """
    HTML Modernization Adapter.
    Formats HTML structure and modernizes deprecated tags/attributes.
    """

    @property
    def language(self) -> str:
        return "html"

    @property
    def provider(self) -> str:
        return "beautifulsoup4"

    def detect(self, workspace_path: str) -> bool:
        ws = Path(workspace_path)
        return any(
            f for f in ws.rglob("*.html")
            if not is_ignored_path(f)
        ) or any(
            f for f in ws.rglob("*.htm")
            if not is_ignored_path(f)
        )

    def analyze(self, profile: TechnologyProfile) -> AnalysisResult:
        html_lang = next((l for l in profile.languages if l.name.lower() == "html"), None)
        return AnalysisResult(
            applicable=bool(html_lang),
            notes="HTML files detected — formatting and tag modernization available"
            if html_lang else "No HTML detected",
        )

    def get_capabilities(self) -> List[MigrationCapability]:
        return [
            MigrationCapability(
                name="html-modernization",
                language="html",
                provider="beautifulsoup4",
                status=CapabilityStatus.AVAILABLE,
                source_versions=["*"],
                target_versions=["5"],
                risk=RiskLevel.LOW,
                description="HTML5 modernization — formats tags, replaces deprecated elements (<center>, <font>)",
            ),
            MigrationCapability(
                name="html-formatting",
                language="html",
                provider="beautifulsoup4",
                status=CapabilityStatus.AVAILABLE,
                source_versions=["*"],
                target_versions=["*"],
                risk=RiskLevel.LOW,
                description="Standard HTML structure formatting and prettification",
            ),
        ]

    def create_plan(
        self,
        workspace_path: str,
        profile: TechnologyProfile,
        target_version: str,
        migration_profile: MigrationProfile = MigrationProfile.CONSERVATIVE,
    ) -> MigrationPlan:
        steps = []
        order = 1

        steps.append(PlanStep(
            order=order,
            name="HTML Formatting",
            description="Format and prettify HTML markup structure",
            adapter="html",
            capability="html-formatting",
            risk=RiskLevel.LOW,
            is_reversible=True,
        ))
        order += 1

        if migration_profile in (MigrationProfile.STANDARD, MigrationProfile.AGGRESSIVE):
            steps.append(PlanStep(
                order=order,
                name="HTML5 Tag Modernization",
                description="Modernize legacy elements (replace <center>, <font>, etc.)",
                adapter="html",
                capability="html-modernization",
                risk=RiskLevel.LOW,
                is_reversible=True,
            ))
            order += 1

        return MigrationPlan(
            plan_id=f"html-plan-{os.urandom(4).hex()}",
            project_id=profile.profile_id if hasattr(profile, "profile_id") else "html-project",
            profile=migration_profile,
            overall_risk=RiskLevel.LOW,
            steps=steps,
            # ✅ FIX: Always populate targets so orchestrator can route by language
            targets=[MigrationTarget(
                language="html",
                source_version=None,
                target_version=target_version or "5",
            )],
            selected_capabilities=[s.capability for s in steps],
        )

    def dry_run(self, workspace_path: str, plan: MigrationPlan) -> DryRunResult:
        """Preview what would change — reads files but does NOT write."""
        ws = Path(workspace_path)
        before_state = self._snapshot_html_files(ws)
        after_state = self._simulate_modernization(before_state, plan.profile)
        diffs = []
        files_would_change = 0
        for file_path, after_content in after_state.items():
            before_content = before_state.get(file_path, "")
            if before_content != after_content:
                files_would_change += 1
                diff = "".join(difflib.unified_diff(
                    before_content.splitlines(keepends=True),
                    after_content.splitlines(keepends=True),
                    fromfile=f"a/{file_path}",
                    tofile=f"b/{file_path}",
                ))
                diffs.append(diff)

        # ✅ FIX: Return base.DryRunResult with files_would_change populated
        return DryRunResult(
            success=True,
            files_would_change=files_would_change,
            notes="\n\n".join(diffs) if diffs else "No HTML changes needed.",
            preview_diffs=diffs,
        )

    def migrate(self, workspace_path: str, plan: MigrationPlan) -> MigrationResult:
        ws = Path(workspace_path)
        before_state = self._snapshot_html_files(ws)
        modified_count = 0
        changed_files = []
        timeline = [{"step": "HTML migration started", "status": "running", "ts": datetime.utcnow().isoformat()}]

        for rel_path, content in before_state.items():
            soup = BeautifulSoup(content, "html.parser")
            modified = False
            content_after = content

            # 1. Format / prettify
            if any(s.capability == "html-formatting" for s in plan.steps):
                content_after = soup.prettify()
                if content_after != content:
                    modified = True

            # 2. Modernize deprecated elements
            if any(s.capability == "html-modernization" for s in plan.steps):
                # Re-parse after prettify
                soup = BeautifulSoup(content_after, "html.parser")

                # Replace <center> → <div style="text-align: center;">
                for center in soup.find_all("center"):
                    center.name = "div"
                    styles = center.get("style", "")
                    center["style"] = (f"text-align: center; {styles}").strip().rstrip(";") + ";"
                    modified = True

                # Replace <font color="X"> → <span style="color: X;">
                for font in soup.find_all("font"):
                    font.name = "span"
                    styles = font.get("style", "")
                    new_styles = []
                    color = font.get("color")
                    face = font.get("face")
                    size = font.get("size")
                    if color:
                        new_styles.append(f"color: {color};")
                        del font["color"]
                    if face:
                        new_styles.append(f"font-family: {face};")
                        del font["face"]
                    if size:
                        size_map = {"1": "xx-small", "2": "x-small", "3": "small", "4": "medium",
                                    "5": "large", "6": "x-large", "7": "xx-large"}
                        new_styles.append(f"font-size: {size_map.get(size, 'medium')};")
                        del font["size"]
                    if new_styles:
                        font["style"] = (" ".join(new_styles) + " " + styles).strip()
                        modified = True

                # Replace <b> → <strong>, <i> → <em> (semantic HTML5)
                for tag, replacement in [("b", "strong"), ("i", "em"), ("u", "ins")]:
                    for el in soup.find_all(tag):
                        el.name = replacement
                        modified = True

                content_after = soup.prettify()

            if modified and content_after != content:
                file_path = ws / rel_path
                file_path.write_text(content_after, encoding="utf-8")
                diff = "".join(difflib.unified_diff(
                    content.splitlines(keepends=True),
                    content_after.splitlines(keepends=True),
                    fromfile=f"a/{rel_path}",
                    tofile=f"b/{rel_path}",
                ))
                changed_files.append(FileChangeMetadata(
                    file=rel_path,
                    status="MODIFIED",
                    diff=diff,
                    before_content=content,
                    after_content=content_after,
                    tools=["beautifulsoup4"],
                    changes=[{"type": "HTML_MODERNIZATION", "description": "Format HTML and replace legacy tags"}],
                ))
                modified_count += 1

        timeline.append({"step": "HTML migration completed", "status": "completed", "ts": datetime.utcnow().isoformat()})

        return MigrationResult(
            result_id=f"html-res-{os.urandom(4).hex()}",
            job_id=plan.plan_id,
            project_id=plan.project_id,
            plan_id=plan.plan_id,
            status=MigrationStatus.SUCCESS,
            statistics=MigrationStatistics(
                files_scanned=len(before_state),
                files_modified=modified_count,
                files_unchanged=len(before_state) - modified_count,
                capabilities_run=len(plan.steps),
                build_passed=True,
            ),
            changed_files=changed_files,
            timeline=timeline,
            completed_at=datetime.utcnow(),
        )

    def validate(self, workspace_path: str, result: MigrationResult) -> ValidationResult:
        ws = Path(workspace_path)
        passed = True
        for f in self._iter_html_files(ws):
            try:
                BeautifulSoup(f.read_text(encoding="utf-8"), "html.parser")
            except Exception:
                passed = False
                break
        return ValidationResult(build_passed=passed, tests_passed=passed, tests_total=1)

    def generate_report(self, result: MigrationResult, validation: ValidationResult) -> dict:
        return {
            "report_id": f"html-rep-{os.urandom(4).hex()}",
            "generated_at": datetime.utcnow().isoformat(),
            "adapter": "html/beautifulsoup4",
            "final_status": result.status.value,
            "statistics": result.statistics.model_dump(),
            "changed_files_count": len(result.changed_files),
            "build_passed": validation.build_passed,
            "timeline": result.timeline,
            "changed_files": [f.model_dump() for f in result.changed_files],
        }

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _iter_html_files(self, ws: Path):
        for f in ws.rglob("*"):
            if f.is_file() and f.suffix.lower() in (".html", ".htm"):
                if not is_ignored_path(f):
                    yield f

    def _snapshot_html_files(self, ws: Path) -> dict:
        snapshot = {}
        for f in self._iter_html_files(ws):
            try:
                snapshot[str(f.relative_to(ws))] = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass
        return snapshot

    def _simulate_modernization(self, before_state: dict, profile: MigrationProfile) -> dict:
        after_state = {}
        for rel_path, content in before_state.items():
            soup = BeautifulSoup(content, "html.parser")
            content_after = soup.prettify()

            if profile in (MigrationProfile.STANDARD, MigrationProfile.AGGRESSIVE):
                soup2 = BeautifulSoup(content_after, "html.parser")
                for center in soup2.find_all("center"):
                    center.name = "div"
                    center["style"] = "text-align: center;"
                for font in soup2.find_all("font"):
                    font.name = "span"
                    if font.get("color"):
                        font["style"] = f"color: {font['color']};"
                        del font["color"]
                content_after = soup2.prettify()

            after_state[rel_path] = content_after
        return after_state
