"""
Dependency Analysis Service — full pipeline orchestrator.

Executes the pipeline:
  1. Detect dependency files
  2. Parse dependencies (per-ecosystem, per-file)
  3. Lookup latest stable version in registry (parallel, per-ecosystem)
  4. Compare current vs. latest (respect constraints)
  5. Build update plan
  6. Apply updates to non-lockfiles
  7. Validate updated files
  8. Return DependencyAnalysisResult

Design decisions:
  - Registry lookups run in a ThreadPoolExecutor for parallel I/O.
  - Lockfiles are detected and reported but NEVER modified.
  - On any registry failure, the dependency is marked LOOKUP_FAILED
    and the pipeline continues (no fail-fast).
  - The service is stateless; instantiate once and call analyze() freely.
"""
from __future__ import annotations

import concurrent.futures
import logging
import re
from pathlib import Path
from typing import List


from app.dependency_analysis.comparator import compare_dependency
from app.dependency_analysis.detector import DependencyFileDetector
from app.dependency_analysis.models import (
    Dependency,
    DependencyAnalysisResult,
    DependencyEcosystem,
    DependencyFile,
    DependencyStatus,
    DependencyUpdateAction,
    ValidationStatus,
)
from app.dependency_analysis.parsers.java_parser import parse_pom_xml
from app.dependency_analysis.parsers.node_parser import parse_package_json
from app.dependency_analysis.parsers.python_parser import (
    parse_pipfile,
    parse_pyproject_toml,
    parse_requirements_txt,
    parse_setup_cfg,
)
from app.dependency_analysis.registry import get_latest_stable_version
from app.dependency_analysis.updater import update_package_json, update_requirements_txt
from app.dependency_analysis.validator import ValidationStatus as VS, validate_file

log = logging.getLogger(__name__)

_MAX_REGISTRY_WORKERS = 25   # I/O-bound: more threads = faster parallel lookups


class DependencyAnalysisService:
    """
    Stateless service that orchestrates the full dependency analysis pipeline.
    """

    def __init__(self) -> None:
        self._detector = DependencyFileDetector()

    # ── Public entry point ────────────────────────────────────────────────────

    def analyze(self, workspace_path: str, plan_only: bool = False) -> DependencyAnalysisResult:
        """
        Run the complete pipeline and return a structured DependencyAnalysisResult.

        plan_only=True  → detect, parse, lookup, compare — but do NOT write any files.
        plan_only=False → full pipeline including applying updates to disk.
        """
        result = DependencyAnalysisResult(workspace_path=workspace_path)

        # Step 1 — detect files
        dep_files = self._detector.detect(workspace_path)
        result.dependency_files = dep_files

        if not dep_files:
            result.warnings.append("No dependency files found in workspace.")
            result.validation_status = ValidationStatus.SKIPPED
            return result

        # Step 2 — parse (only non-lockfiles)
        all_deps: List[Dependency] = []
        seen_deps = set()
        for dep_file in dep_files:
            if dep_file.is_lockfile:
                result.warnings.append(
                    f"Lockfile detected and skipped: {dep_file.path}"
                )
                continue
            parsed = self._parse_file(workspace_path, dep_file)
            for d in parsed:
                # Set correct relative source_file path
                d.source_file = dep_file.path
                # Deduplicate by (name, project_name)
                dep_key = (d.name.lower(), (d.project_name or "").lower())
                if dep_key not in seen_deps:
                    seen_deps.add(dep_key)
                    all_deps.append(d)

        result.dependencies = all_deps

        if not all_deps:
            result.warnings.append("No parseable dependencies found (only lockfiles?).")
            result.validation_status = ValidationStatus.SKIPPED
            return result

        # Step 3 — resolve latest versions in parallel
        self._resolve_latest_versions(all_deps)

        # Step 4 — compare current vs latest (sets status on each dep)
        for dep in all_deps:
            compare_dependency(dep)

        # Step 5 — partition results
        for dep in all_deps:
            if dep.status == DependencyStatus.UP_TO_DATE:
                result.up_to_date.append(dep.name)
            elif dep.status == DependencyStatus.UPDATE_AVAILABLE:
                result.outdated.append(dep.name)
                result.proposed_updates.append(DependencyUpdateAction(
                    dependency_name=dep.name,
                    source_file=dep.source_file,
                    ecosystem=dep.ecosystem,
                    current_version=dep.current_version,
                    proposed_version=dep.latest_stable_version,  # type: ignore[arg-type]
                    action="UPDATE",
                    reason=dep.reason,
                ))
            elif dep.status == DependencyStatus.CONSTRAINT_BLOCKED:
                result.constraint_blocked.append(dep.name)
                result.warnings.append(
                    f"{dep.name}: {dep.reason}"
                )
            else:
                result.lookup_failed.append(dep.name)
                result.warnings.append(
                    f"{dep.name}: registry lookup failed or version invalid."
                )

        # Step 6 — apply updates (skip in plan_only mode)
        changed_files: list[str] = []
        if not plan_only:
            changed_files = self._apply_updates(workspace_path, all_deps, dep_files)
        result.changed_files = changed_files

        # Step 7 — validate
        overall_status = ValidationStatus.SKIPPED
        for file_path in changed_files:
            abs_path = str(Path(workspace_path) / file_path)
            vstatus, verrors = validate_file(abs_path)
            if verrors:
                result.validation_errors.extend(verrors)
            if vstatus == VS.FAILED:
                overall_status = ValidationStatus.FAILED
            elif vstatus == VS.PASSED and overall_status != ValidationStatus.FAILED:
                overall_status = ValidationStatus.PASSED

        result.validation_status = overall_status
        return result

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _parse_file(self, workspace_path: str, dep_file: DependencyFile) -> List[Dependency]:
        """Dispatch to the correct parser based on filename and ecosystem."""
        abs_path = str(Path(workspace_path) / dep_file.path)
        name = Path(dep_file.path).name.lower()

        try:
            if dep_file.ecosystem == DependencyEcosystem.PYTHON:
                if name in ("requirements.txt", "requirements-dev.txt",
                            "requirements-test.txt", "requirements-prod.txt"):
                    return parse_requirements_txt(abs_path)
                if name == "pyproject.toml":
                    return parse_pyproject_toml(abs_path)
                if name == "setup.cfg":
                    return parse_setup_cfg(abs_path)
                if name == "pipfile":
                    return parse_pipfile(abs_path)

            elif dep_file.ecosystem == DependencyEcosystem.NODE:
                if name == "package.json":
                    return parse_package_json(abs_path)

            elif dep_file.ecosystem == DependencyEcosystem.JAVA:
                if name == "pom.xml":
                    return parse_pom_xml(abs_path)

            elif dep_file.ecosystem == DependencyEcosystem.DOTNET:
                if name == "packages.config":
                    return parse_packages_config(abs_path)
                elif name.endswith(".csproj"):
                    return parse_csproj(abs_path)

        except Exception as exc:
            log.warning("Parser error for %s: %s", dep_file.path, exc)

        return []

    def _resolve_latest_versions(self, deps: List[Dependency]) -> None:
        """Parallel registry lookup for all dependencies."""
        def _lookup(dep: Dependency) -> None:
            dep.latest_stable_version = get_latest_stable_version(
                dep.name, dep.ecosystem
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_REGISTRY_WORKERS) as pool:
            list(pool.map(_lookup, deps))   # consume to propagate exceptions

    def _apply_updates(
        self,
        workspace_path: str,
        all_deps: List[Dependency],
        dep_files: List[DependencyFile],
    ) -> List[str]:
        """
        Group proposed updates by source file and apply each file's updater.
        Returns relative paths of files that were actually changed.
        """
        # Group deps by source_file (relative)
        by_file: dict[str, List[Dependency]] = {}
        for dep in all_deps:
            by_file.setdefault(dep.source_file, []).append(dep)

        changed: List[str] = []

        # Build a set of lockfile paths for fast lookup
        lockfile_paths = {df.path for df in dep_files if df.is_lockfile}

        for rel_path, deps in by_file.items():
            if rel_path in lockfile_paths:
                continue  # never touch lockfiles

            abs_path = str(Path(workspace_path) / rel_path)
            name = Path(rel_path).name.lower()
            file_changed = False

            if name in ("requirements.txt", "requirements-dev.txt",
                        "requirements-test.txt", "requirements-prod.txt"):
                file_changed = update_requirements_txt(abs_path, deps)

            elif name == "package.json":
                file_changed = update_package_json(abs_path, deps)

            # pyproject.toml / pom.xml / setup.cfg updates not yet implemented
            # (no unsafe text replacement on complex formats)

            if file_changed:
                changed.append(rel_path)

        return changed


def parse_packages_config(file_path: str) -> List[Dependency]:
    """Parse packages.config NuGet dependencies."""
    deps: List[Dependency] = []
    path = Path(file_path)
    rel = path.name

    # Resolve project name
    project_name = None
    try:
        csproj_files = list(path.parent.glob("*.csproj"))
        if csproj_files:
            project_name = csproj_files[0].stem
        else:
            project_name = path.parent.name
    except Exception:
        project_name = path.parent.name

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r'<package\s+([^>]+?)/?>', content, re.IGNORECASE):
            attrs = dict(re.findall(r'([\w\-.:]+)\s*=\s*[\'"]([^\'"]+)[\'"]', m.group(1)))
            name = attrs.get("id")
            version = attrs.get("version")
            if name:
                deps.append(Dependency(
                    name=name,
                    current_version=version,
                    version_constraint=f"=={version}" if version else None,
                    source_file=rel,
                    ecosystem=DependencyEcosystem.DOTNET,
                    status=DependencyStatus.LOOKUP_FAILED,
                    project_name=project_name,
                ))
    except Exception:
        pass

    return deps


def parse_csproj(file_path: str) -> List[Dependency]:
    """Parse PackageReference tags and legacy HintPath NuGet references from .csproj."""
    deps: List[Dependency] = []
    path = Path(file_path)
    rel = path.name
    project_name = path.stem

    try:
        content = path.read_text(encoding="utf-8", errors="replace")

        # 1. PackageReference tags
        matches = re.finditer(r'<PackageReference\s+([^>]+?)(?:/>|>(.*?)</PackageReference>)', content, re.DOTALL | re.IGNORECASE)
        for m in matches:
            attrs_str = m.group(1)
            inner_content = m.group(2) if m.group(2) else ""
            attrs = dict(re.findall(r'([\w\-.:]+)\s*=\s*[\'"]([^\'"]+)[\'"]', attrs_str))
            name = attrs.get("Include") or attrs.get("Update")
            if not name:
                continue
            version = attrs.get("Version")
            if not version and inner_content:
                v_match = re.search(r'<Version>\s*(.*?)\s*</Version>', inner_content, re.IGNORECASE)
                if v_match:
                    version = v_match.group(1).strip()
            deps.append(Dependency(
                name=name,
                current_version=version,
                version_constraint=f"=={version}" if version else None,
                source_file=rel,
                ecosystem=DependencyEcosystem.DOTNET,
                status=DependencyStatus.LOOKUP_FAILED,
                project_name=project_name,
            ))

        # 2. Legacy Reference tags with HintPath pointing to packages/
        ref_matches = re.finditer(r'<Reference\s+([^>]+?)>(.*?)</Reference>', content, re.DOTALL | re.IGNORECASE)
        for m in ref_matches:
            attrs_str = m.group(1)
            inner_content = m.group(2)

            hint_match = re.search(r'<HintPath>\s*(.*?)\s*</HintPath>', inner_content, re.IGNORECASE)
            if not hint_match:
                continue

            hint_path = hint_match.group(1).strip().replace("\\", "/")
            if "packages/" not in hint_path.lower():
                continue

            m_pkg = re.search(r'packages/([^/]+)', hint_path, re.IGNORECASE)
            if not m_pkg:
                continue

            folder_name = m_pkg.group(1)
            m_split = re.match(r"^([a-zA-Z0-9._\-]+?)\.([0-9]+(?:\.[0-9]+)*[a-zA-Z0-9.\-]*)$", folder_name)
            if m_split:
                pkg_name = m_split.group(1)
                pkg_version = m_split.group(2)
                deps.append(Dependency(
                    name=pkg_name,
                    current_version=pkg_version,
                    version_constraint=f"=={pkg_version}",
                    source_file=rel,
                    ecosystem=DependencyEcosystem.DOTNET,
                    status=DependencyStatus.LOOKUP_FAILED,
                    project_name=project_name,
                ))
    except Exception:
        pass

    return deps

