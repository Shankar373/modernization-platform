"""
Migration Orchestrator — coordinates the full migration pipeline.

The orchestrator delegates all language-specific logic to adapters.
It does NOT contain language-specific if/elif routing.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional



from app.adapters.base import MigrationAdapter, adapter_registry, CSharpRoslynAdapter
from app.adapters.java.adapter import JavaOpenRewriteAdapter
from app.adapters.python.adapter import PythonRuffAdapter
from app.adapters.typescript.adapter import TypeScriptAdapter
from app.adapters.html.adapter import HtmlModernizationAdapter
from app.adapters.css.adapter import CssModernizationAdapter
from app.adapters.json.adapter import JsonFormatterAdapter
from app.adapters.yaml.adapter import YamlFormatterAdapter
from app.adapters.markdown.adapter import MarkdownFormatterAdapter
from app.adapters.javascript.adapter import JavaScriptPrettierAdapter
from app.adapters.go.adapter import GoAdapter
from app.adapters.php.adapter import PhpAdapter
from app.adapters.shell.adapter import ShellAdapter
from app.adapters.generic.adapter import GenericFallbackAdapter

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


def _coerce_profile(value):
    """Accept a MigrationProfile enum or its string value; fall back to STANDARD."""
    if isinstance(value, MigrationProfile):
        return value
    if isinstance(value, str):
        try:
            return MigrationProfile(value.strip().upper())
        except ValueError:
            pass
    return MigrationProfile.STANDARD


# ── Adapter Registry & Dynamic Discovery ─────────────────────────────────────
# All language connectors register here for automatic execution during migrations.

_ADAPTERS: list[MigrationAdapter] = [
    JavaOpenRewriteAdapter(),
    PythonRuffAdapter(),
    CSharpRoslynAdapter(),    # C# Roslyn analyzer + AST file-scoped namespace modernization
    TypeScriptAdapter(),     # TypeScript-specific: var→let, require→import, ts-ignore fixes
    JavaScriptPrettierAdapter(),  # JS/TS formatting via Prettier
    HtmlModernizationAdapter(),
    CssModernizationAdapter(),
    JsonFormatterAdapter(),
    YamlFormatterAdapter(),
    MarkdownFormatterAdapter(),
    GoAdapter(),
    PhpAdapter(),
    ShellAdapter(),
    GenericFallbackAdapter(),
]

adapter_registry.register_all(_ADAPTERS)

# Register live adapter capabilities into global capability registry
for adapter in _ADAPTERS:
    for cap in adapter.get_capabilities():
        registry.register(cap)



_SKIP_SCAN_DIRS = {"node_modules", ".venv", "venv", "__pycache__", ".git",
                   "dist", "build", ".next", ".pytest_cache", ".mypy_cache"}

# ── Extension → adapter language map (used in fast pre-scan) ─────────────────
_EXT_TO_LANG: dict[str, set[str]] = {
    ".py":        {"python"},
    ".html":      {"html"}, ".htm": {"html"},
    ".css":       {"css"},  ".scss": {"css"}, ".sass": {"css"},
    ".js":        {"javascript"}, ".jsx": {"javascript"},
    ".ts":        {"typescript", "javascript"}, ".tsx": {"typescript", "javascript"},
    ".mjs":       {"javascript"}, ".cjs": {"javascript"},
    ".json":      {"json"},
    ".yaml":      {"yaml"}, ".yml": {"yaml"},
    ".md":        {"markdown"}, ".markdown": {"markdown"},
    ".java":      {"java"},
    ".cs":        {"csharp"}, ".csproj": {"csharp"},
    ".go":        {"go"},
    ".php":       {"php"}, ".phtml": {"php"},
    ".sh":        {"shell"}, ".bash": {"shell"}, ".zsh": {"shell"},
    ".c":         {"generic"}, ".cpp": {"generic"},
    ".rs":        {"generic"}, ".kt": {"generic"}, ".swift": {"generic"},

    ".sql":       {"generic"}, ".toml": {"generic"}, ".xml": {"generic"},
}



def _is_skip_dir(p: str) -> bool:
    pl = p.lower()
    return (pl in {"node_modules", ".venv", "venv", "__pycache__", ".git", "dist", "build", ".next", ".pytest_cache", ".mypy_cache", "site-packages", "vendor"}
            or pl.startswith(".venv") or "venv" in pl or "site-packages" in pl)


def _collect_extensions(workspace_path: str) -> frozenset[str]:
    """
    Single O(n) filesystem walk → frozenset of file extensions present.
    Used by get_applicable_adapters() to avoid one rglob per adapter.
    """
    exts: set[str] = set()
    ws = Path(workspace_path)
    for f in ws.rglob("*"):
        if f.is_file() and not any(_is_skip_dir(part) for part in f.parts):
            exts.add(f.suffix.lower())
    return frozenset(exts)



class MigrationOrchestrator:
    """
    Coordinates the end-to-end migration pipeline.

    Flow:
    scan → profile → find adapters → assess → plan → dry_run → migrate → validate → report

    Language-specific logic lives entirely in adapters — this class is language-agnostic.
    """

    def __init__(self):
        self.scanner = UniversalScanner()
        # In-process cache: workspace_path → (frozenset[extensions], list[adapter])
        self._adapter_cache: dict[str, tuple[frozenset, list]] = {}
        # In-process analysis cache: workspace_path → assessment dict
        self._analysis_cache: dict[str, dict] = {}

    def scan(self, workspace_path: str) -> TechnologyProfile:
        """Step 1: Scan the repository and build a technology profile."""
        return self.scanner.scan(workspace_path)

    def get_applicable_adapters(self, workspace_path: str) -> list[MigrationAdapter]:
        """
        Return all adapters that apply to this workspace.

        Optimisation: one filesystem walk builds the extension set; each
        adapter's detect() is ONLY called when its known extensions are present,
        and the result is cached for the lifetime of this request.
        """
        if workspace_path in self._adapter_cache:
            _, adapters = self._adapter_cache[workspace_path]
            return adapters

        exts = _collect_extensions(workspace_path)

        # Pre-filter: only call detect() if the extension map suggests this language exists
        candidates: list[MigrationAdapter] = []
        for adapter in _ADAPTERS:
            # Find which extensions map to this adapter's language
            adapter_exts = {e for e, langs in _EXT_TO_LANG.items() if adapter.language in langs}
            if adapter_exts and not (exts & adapter_exts):
                continue  # fast skip — no relevant files present
            # Full detect() only for adapters that might apply
            if adapter.detect(workspace_path):
                candidates.append(adapter)

        self._adapter_cache[workspace_path] = (exts, candidates)
        return candidates


    def get_assessment(self, workspace_path: str, profile: TechnologyProfile) -> dict:
        """
        Step 2: Assess the repository — return capabilities, unsupported languages,
        and target recommendations without modifying anything.
        """
        applicable_adapters = self.get_applicable_adapters(workspace_path)
        supported_languages = {a.language for a in applicable_adapters}

        # Normalize scanner language names to adapter language keys.
        _LANG_ALIASES = {
            "c#": "csharp", "vb.net": "csharp", "f#": "csharp",
            "c": "generic", "c++": "generic", "cpp": "generic", "cxx": "generic",
            "kotlin": "generic", "swift": "generic", "rust": "generic", "rs": "generic",
            "sql": "generic", "obj-c": "generic", "objective-c": "generic",
            "js": "javascript", "node": "javascript", "nodejs": "javascript",
            "ts": "typescript", "cobol": "cobol", "ruby": "ruby", "r": "generic",
            "lua": "generic", "fortran": "generic", "pascal": "generic",
        }

        detected_languages = []
        for lang in [l.name for l in profile.languages]:
            key = lang.lower().strip()
            detected_languages.append(_LANG_ALIASES.get(key, key))

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

    def dry_run_all(
        self,
        workspace_path: str,
        project_id: str,
        migration_profile: MigrationProfile = MigrationProfile.STANDARD,
    ) -> dict:
        """
        Dry-run ALL applicable adapters in parallel — no files are modified.

        Returns a preview dict with:
        - per_adapter: list of {language, adapter, files_would_change, notes, warnings}
        - total_files_would_change: int
        - adapters_found: list[str]
        - summary: human-readable description
        """
        import concurrent.futures

        migration_profile = _coerce_profile(migration_profile)

        adapters = self.get_applicable_adapters(workspace_path)
        if not adapters:
            return {
                "success": False,
                "total_files_would_change": 0,
                "adapters_found": [],
                "per_adapter": [],
                "summary": "No applicable adapters found for this workspace.",
            }

        profile = self.scanner.scan(workspace_path)

        def _dry_run_one(adapter: "MigrationAdapter") -> dict:
            lang = adapter.language
            try:
                plan = adapter.create_plan(workspace_path, profile, "latest", migration_profile)
                result = adapter.dry_run(workspace_path, plan)
                return {
                    "language": lang,
                    "adapter": adapter.provider,
                    "files_would_change": getattr(result, "files_would_change", 0),
                    "notes": getattr(result, "notes", ""),
                    "warnings": getattr(result, "warnings", []),
                    "success": getattr(result, "success", True),
                }
            except Exception as exc:
                return {
                    "language": lang,
                    "adapter": adapter.provider,
                    "files_would_change": 0,
                    "notes": f"Dry run skipped: {exc}",
                    "warnings": [str(exc)],
                    "success": False,
                }

        max_workers = min(len(adapters), 8)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            per_adapter = list(pool.map(_dry_run_one, adapters))

        total = sum(r["files_would_change"] for r in per_adapter)
        adapter_names = [r["language"] for r in per_adapter if r["success"]]

        return {
            "success": True,
            "total_files_would_change": total,
            "adapters_found": adapter_names,
            "per_adapter": per_adapter,
            "workspace_path": workspace_path,
            "project_id": project_id,
            "migration_profile": migration_profile.value if hasattr(migration_profile, "value") else str(migration_profile),
            "summary": (
                f"{len(adapter_names)} adapter(s) will process {total} file(s): "
                + ", ".join(adapter_names)
            ),
        }

    def migrate_all(
        self,
        workspace_path: str,
        project_id: str,
        migration_profile: MigrationProfile = MigrationProfile.STANDARD,
    ) -> MigrationResult:
        """
        Full-application migration: auto-detect ALL languages and run every
        applicable adapter IN PARALLEL. Returns one combined MigrationResult.
        """
        import concurrent.futures
        import threading

        migration_profile = _coerce_profile(migration_profile)

        combined_id = str(uuid.uuid4())
        timeline: list[dict] = [
            {"step": "Full-app migration started", "status": "running", "ts": datetime.utcnow().isoformat()}
        ]
        timeline_lock = threading.Lock()

        adapters = self.get_applicable_adapters(workspace_path)
        if not adapters:
            return MigrationResult(
                result_id=combined_id, job_id=combined_id, project_id=project_id, plan_id=combined_id,
                status=MigrationStatus.NOT_SUPPORTED,
                warnings=["No applicable adapters found for this workspace."],
            )

        profile = self.scanner.scan(workspace_path)

        def _run_adapter(adapter: "MigrationAdapter"):
            lang = adapter.language
            with timeline_lock:
                timeline.append({"step": f"[{lang}] Starting", "status": "running",
                                  "ts": datetime.utcnow().isoformat()})
            try:
                plan = adapter.create_plan(workspace_path, profile, "latest", migration_profile)
                result = adapter.migrate(workspace_path, plan)
                validation = adapter.validate(workspace_path, result)

                # Tag files with adapter language
                for cf in result.changed_files:
                    cf.tools = cf.tools or []
                    if lang not in cf.tools:
                        cf.tools.insert(0, lang)

                with timeline_lock:
                    timeline.append({
                        "step": f"[{lang}] Done — {result.statistics.files_modified} file(s) modified",
                        "status": "completed", "ts": datetime.utcnow().isoformat(),
                    })
                return {"lang": lang, "adapter": adapter.provider, "result": result,
                        "validation": validation, "error": None}
            except Exception as exc:
                with timeline_lock:
                    timeline.append({"step": f"[{lang}] Error: {exc}", "status": "error",
                                     "ts": datetime.utcnow().isoformat()})
                return {"lang": lang, "adapter": adapter.provider, "result": None,
                        "validation": None, "error": str(exc)}

        # Run adapters in parallel — max 8 workers, I/O-bound safe
        max_workers = min(len(adapters), 8)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_run_adapter, a): a for a in adapters}
            adapter_results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # Merge results
        total_scanned = total_modified = total_unchanged = total_caps = 0
        all_changed_files: list = []
        all_warnings: list[str] = []
        all_build_passed = True
        per_language: list[dict] = []

        for ar in adapter_results:
            if ar["error"]:
                all_warnings.append(f"{ar['lang']} adapter failed: {ar['error']}")
                continue
            result = ar["result"]
            validation = ar["validation"]
            all_changed_files.extend(result.changed_files)
            total_scanned   += result.statistics.files_scanned
            total_modified  += result.statistics.files_modified
            total_unchanged += result.statistics.files_unchanged
            total_caps      += result.statistics.capabilities_run
            all_warnings    += result.warnings
            if not validation.build_passed:
                all_build_passed = False
            per_language.append({
                "language": ar["lang"], "adapter": ar["adapter"],
                "files_modified": result.statistics.files_modified,
                "status": result.status.value,
            })

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
            completed_at=datetime.utcnow(),
            logs={"per_language": json.dumps(per_language)},
        )




    def generate_report(self, workspace_path: str, plan: Optional[MigrationPlan], result: MigrationResult) -> dict:
        """Step 6: Generate the migration report."""
        if not plan:
            # Combined / Multi-language report
            return {
                "report_id": f"combined-rep-{uuid.uuid4().hex[:8]}",
                "generated_at": datetime.utcnow().isoformat(),
                "adapter": "orchestrator/combined",
                "final_status": result.status.value,
                "statistics": result.statistics.model_dump(),
                "changed_files_count": len(result.changed_files),
                "build_passed": result.statistics.build_passed,
                "timeline": result.timeline,
                "changed_files": [f.model_dump() for f in result.changed_files],
            }

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
        return adapter_registry.get_by_language(language)


    def _find_adapter_for_plan(self, plan: Optional[MigrationPlan]) -> Optional[MigrationAdapter]:
        """Route to adapter by targets[0].language; fall back to steps[0].adapter (language or engine name)."""
        if not plan:
            return None
        # Primary: use targets list
        if plan.targets:
            adapter = self._find_adapter(plan.targets[0].language)
            if adapter:
                return adapter
        # Fallback: infer language from the first step's adapter field (language or engine name)
        if plan.steps:
            adapter = self._find_adapter(plan.steps[0].adapter)
            if adapter:
                return adapter
            adapter = adapter_registry.get_by_engine(plan.steps[0].adapter)
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
