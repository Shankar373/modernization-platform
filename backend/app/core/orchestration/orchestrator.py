"""
Migration Orchestrator — coordinates the full migration pipeline.

The orchestrator delegates all language-specific logic to adapters.
It does NOT contain language-specific if/elif routing.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from app.adapters.base import MigrationAdapter
from app.adapters.java.adapter import JavaOpenRewriteAdapter
from app.adapters.python.adapter import PythonRuffAdapter
from app.adapters.html.adapter import HtmlModernizationAdapter
from app.adapters.css.adapter import CssModernizationAdapter
from app.adapters.json.adapter import JsonFormatterAdapter
from app.adapters.yaml.adapter import YamlFormatterAdapter
from app.adapters.markdown.adapter import MarkdownFormatterAdapter
from app.adapters.javascript.adapter import JavaScriptPrettierAdapter
from app.capabilities.registry import registry
from app.core.domain.models import (
    CapabilityStatus,
    MigrationPlan,
    MigrationProfile,
    MigrationResult,
    MigrationStatistics,
    MigrationStatus,
    TechnologyProfile,
)
from app.discovery.scanner import UniversalScanner


# ── Adapter Registry ──────────────────────────────────────────────────────────
# Add new adapters here — the orchestrator logic stays language-agnostic.

_ADAPTERS: list[MigrationAdapter] = [
    JavaOpenRewriteAdapter(),
    PythonRuffAdapter(),
    HtmlModernizationAdapter(),
    CssModernizationAdapter(),
    JsonFormatterAdapter(),
    YamlFormatterAdapter(),
    MarkdownFormatterAdapter(),
    JavaScriptPrettierAdapter(),
]



class MigrationOrchestrator:
    """
    Coordinates the end-to-end migration pipeline.

    Flow:
    scan → profile → find adapters → assess → plan → dry_run → migrate → validate → report

    Language-specific logic lives entirely in adapters — this class is language-agnostic.
    """

    def __init__(self):
        self.scanner = UniversalScanner()

    def scan(self, workspace_path: str) -> TechnologyProfile:
        """Step 1: Scan the repository and build a technology profile."""
        return self.scanner.scan(workspace_path)

    def get_applicable_adapters(self, workspace_path: str) -> list[MigrationAdapter]:
        """Return all adapters that claim applicability to this workspace."""
        return [a for a in _ADAPTERS if a.detect(workspace_path)]

    def get_assessment(self, workspace_path: str, profile: TechnologyProfile) -> dict:
        """
        Step 2: Assess the repository — return capabilities, unsupported languages,
        and target recommendations without modifying anything.
        """
        applicable_adapters = self.get_applicable_adapters(workspace_path)
        supported_languages = {a.language for a in applicable_adapters}

        detected_languages = [l.name.lower() for l in profile.languages]
        unsupported = [
            lang for lang in detected_languages
            if lang not in supported_languages
        ]

        capabilities = []
        for adapter in applicable_adapters:
            capabilities.extend(adapter.get_capabilities())

        # Add NOT_AVAILABLE stubs for unsupported detected languages
        for lang in unsupported:
            lang_caps = registry.get_for_language(lang)
            if not lang_caps:
                capabilities.append({
                    "language": lang,
                    "status": CapabilityStatus.NOT_AVAILABLE.value,
                    "description": f"No migration connector available for {lang}.",
                    "notes": "Assessment and roadmap only.",
                })
            else:
                capabilities.extend(lang_caps)

        return {
            "profile": profile.model_dump(),
            "supported_languages": list(supported_languages),
            "unsupported_languages": unsupported,
            "capabilities": [
                c.model_dump() if hasattr(c, "model_dump") else c
                for c in capabilities
            ],
            "target_recommendations": self._recommend_targets(profile, applicable_adapters),
        }

    def create_plan(
        self,
        workspace_path: str,
        profile: TechnologyProfile,
        language: str,
        target_version: str,
        migration_profile: MigrationProfile = MigrationProfile.CONSERVATIVE,
    ) -> Optional[MigrationPlan]:
        """Step 3: Build a migration plan using the appropriate adapter."""
        adapter = self._find_adapter(language)
        if not adapter:
            return None
        return adapter.create_plan(workspace_path, profile, target_version, migration_profile)

    def dry_run(self, workspace_path: str, plan: MigrationPlan) -> dict:
        """Step 4: Execute a dry run via the appropriate adapter."""
        adapter = self._find_adapter_for_plan(plan)
        if not adapter:
            language = plan.targets[0].language if plan.targets else "unknown"
            return {"success": False, "notes": f"No adapter for language: {language}"}
        result = adapter.dry_run(workspace_path, plan)
        return {
            "success": result.success,
            # ✅ FIX: safe getattr — older adapters may not have files_would_change
            "files_would_change": getattr(result, "files_would_change", 0),
            "notes": result.notes,
            "warnings": getattr(result, "warnings", []),
        }

    def migrate(self, workspace_path: str, plan: MigrationPlan) -> MigrationResult:
        """Step 5: Execute the actual migration (only after user approval)."""
        adapter = self._find_adapter_for_plan(plan)
        if not adapter:
            language = plan.targets[0].language if plan.targets else "unknown"
            return MigrationResult(
                result_id="",
                job_id=plan.plan_id,
                project_id=plan.project_id,
                plan_id=plan.plan_id,
                status=MigrationStatus.NOT_SUPPORTED,
                warnings=[f"No adapter available for language: {language}"],
            )
        result = adapter.migrate(workspace_path, plan)
        validation = adapter.validate(workspace_path, result)

        # Update result status based on validation
        if result.status == MigrationStatus.SUCCESS and not validation.build_passed:
            result.status = MigrationStatus.PARTIALLY_SUCCESSFUL

        result.statistics.build_passed = validation.build_passed
        result.statistics.tests_passed = validation.tests_passed
        result.statistics.tests_failed = validation.tests_failed
        result.logs["validation"] = validation.raw_output

        return result

    def migrate_all(
        self,
        workspace_path: str,
        project_id: str,
        migration_profile: MigrationProfile = MigrationProfile.STANDARD,
    ) -> MigrationResult:
        """
        Full-application migration: auto-detect ALL languages and run every
        applicable adapter. Returns one combined MigrationResult.
        """
        combined_id = str(uuid.uuid4())
        timeline: list[dict] = [
            {"step": "Full-app migration started", "status": "running", "ts": datetime.utcnow().isoformat()}
        ]

        adapters = self.get_applicable_adapters(workspace_path)
        if not adapters:
            return MigrationResult(
                result_id=combined_id, job_id=combined_id, project_id=project_id, plan_id=combined_id,
                status=MigrationStatus.NOT_SUPPORTED,
                warnings=["No applicable adapters found for this workspace."],
            )

        profile = self.scanner.scan(workspace_path)

        total_scanned = total_modified = total_unchanged = total_caps = 0
        all_changed_files = []
        all_warnings: list[str] = []
        all_build_passed = True
        per_language: list[dict] = []

        for adapter in adapters:
            lang = adapter.language
            timeline.append({"step": f"[{lang}] Starting", "status": "running", "ts": datetime.utcnow().isoformat()})
            try:
                plan = adapter.create_plan(workspace_path, profile, "latest", migration_profile)
                result = adapter.migrate(workspace_path, plan)
                validation = adapter.validate(workspace_path, result)

                # Tag each changed file with the adapter that modified it
                for cf in result.changed_files:
                    cf.tools = cf.tools or []
                    if lang not in cf.tools:
                        cf.tools.insert(0, lang)
                    all_changed_files.append(cf)

                total_scanned   += result.statistics.files_scanned
                total_modified  += result.statistics.files_modified
                total_unchanged += result.statistics.files_unchanged
                total_caps      += result.statistics.capabilities_run
                all_warnings    += result.warnings
                if not validation.build_passed:
                    all_build_passed = False

                per_language.append({
                    "language": lang, "adapter": adapter.provider,
                    "files_modified": result.statistics.files_modified,
                    "status": result.status.value,
                })
                timeline.append({"step": f"[{lang}] Done — {result.statistics.files_modified} file(s) modified",
                                  "status": "completed", "ts": datetime.utcnow().isoformat()})
            except Exception as exc:
                timeline.append({"step": f"[{lang}] Error: {exc}", "status": "error",
                                  "ts": datetime.utcnow().isoformat()})
                all_warnings.append(f"{lang} adapter failed: {exc}")

        timeline.append({"step": "Full-app migration completed", "status": "completed",
                         "ts": datetime.utcnow().isoformat()})

        final_status = (
            MigrationStatus.SUCCESS if total_modified > 0 and all_build_passed
            else MigrationStatus.PARTIALLY_SUCCESSFUL if total_modified > 0
            else MigrationStatus.PARTIALLY_SUCCESSFUL
        )

        return MigrationResult(
            result_id=combined_id, job_id=combined_id,
            project_id=project_id, plan_id=combined_id,
            status=final_status,
            statistics=MigrationStatistics(
                files_scanned=total_scanned, files_modified=total_modified,
                files_unchanged=total_unchanged, capabilities_run=total_caps,
                build_passed=all_build_passed,
            ),
            changed_files=all_changed_files,
            warnings=all_warnings,
            timeline=timeline,
            completed_at=datetime.utcnow(),
            logs={"per_language": per_language},
        )



    def generate_report(self, workspace_path: str, plan: MigrationPlan, result: MigrationResult) -> dict:
        """Step 6: Generate the migration report."""
        adapter = self._find_adapter_for_plan(plan)
        if not adapter:
            language = plan.targets[0].language if plan.targets else "unknown"
            return {"status": "NOT_SUPPORTED", "error": f"No adapter for {language}"}

        from app.adapters.base import ValidationResult
        validation = ValidationResult(
            build_passed=result.statistics.build_passed or False,
            tests_passed=result.statistics.tests_passed,
            tests_total=result.statistics.tests_total,
            tests_failed=result.statistics.tests_failed,
        )
        return adapter.generate_report(result, validation)

    def _find_adapter(self, language: Optional[str]) -> Optional[MigrationAdapter]:
        if not language:
            return None
        for adapter in _ADAPTERS:
            if adapter.language.lower() == language.lower():
                return adapter
        return None

    def _find_adapter_for_plan(self, plan: MigrationPlan) -> Optional[MigrationAdapter]:
        """Route to adapter by targets[0].language; fall back to steps[0].adapter."""
        # Primary: use targets list
        if plan.targets:
            adapter = self._find_adapter(plan.targets[0].language)
            if adapter:
                return adapter
        # Fallback: infer language from the first step's adapter field
        if plan.steps:
            adapter = self._find_adapter(plan.steps[0].adapter)
            if adapter:
                return adapter
        return None

    def _recommend_targets(self, profile: TechnologyProfile, adapters: list[MigrationAdapter]) -> list[dict]:
        recommendations = []
        for lang in profile.languages:
            adapter = self._find_adapter(lang.name)
            if not adapter:
                continue
            for cap in adapter.get_capabilities():
                if cap.target_versions:
                    recommendations.append({
                        "language": lang.name,
                        "source_version": lang.version,
                        "recommended_target": cap.target_versions[-1],
                        "capability": cap.name,
                        "risk": cap.risk.value,
                        "description": cap.description,
                    })
                    break
        return recommendations
