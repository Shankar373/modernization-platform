"""
Tests for the Dependency Analysis pipeline.

All registry / network calls are MOCKED — no internet access required.
Run from backend/ directory:
    python -m pytest tests/unit/test_dependency_analysis.py -v
"""
from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

# Ensure 'app' is importable when running from backend/
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from app.dependency_analysis.comparator import compare_dependency
from app.dependency_analysis.detector import DependencyFileDetector
from app.dependency_analysis.models import (
    Dependency,
    DependencyEcosystem,
    DependencyFile,
    DependencyStatus,
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
from app.dependency_analysis.registry import _is_stable, get_latest_stable_version
from app.dependency_analysis.updater import update_requirements_txt
from app.dependency_analysis.validator import validate_requirements_txt


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_dep(
    name: str,
    current: Optional[str],
    latest: Optional[str],
    constraint: Optional[str] = None,
    ecosystem: DependencyEcosystem = DependencyEcosystem.PYTHON,
) -> Dependency:
    return Dependency(
        name=name,
        current_version=current,
        latest_stable_version=latest,
        version_constraint=constraint,
        source_file="requirements.txt",
        ecosystem=ecosystem,
        status=DependencyStatus.LOOKUP_FAILED,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 1. Dependency File Detection
# ══════════════════════════════════════════════════════════════════════════════

class TestDependencyFileDetector:

    def test_detects_requirements_txt(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("requests==2.28.0\n")
        files = DependencyFileDetector().detect(str(tmp_path))
        paths = [f.path for f in files]
        assert "requirements.txt" in paths

    def test_detects_package_json(self, tmp_path):
        (tmp_path / "package.json").write_text('{"dependencies":{}}')
        files = DependencyFileDetector().detect(str(tmp_path))
        assert any(f.path == "package.json" for f in files)

    def test_detects_pom_xml(self, tmp_path):
        (tmp_path / "pom.xml").write_text("<project></project>")
        files = DependencyFileDetector().detect(str(tmp_path))
        assert any(f.path == "pom.xml" for f in files)

    def test_lockfiles_flagged(self, tmp_path):
        (tmp_path / "package-lock.json").write_text("{}")
        (tmp_path / "yarn.lock").write_text("")
        (tmp_path / "pnpm-lock.yaml").write_text("")
        (tmp_path / "Pipfile.lock").write_text("{}")
        files = DependencyFileDetector().detect(str(tmp_path))
        for f in files:
            assert f.is_lockfile, f"{f.path} should be a lockfile"

    def test_multiple_req_files(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("django==3.2\n")
        (tmp_path / "requirements-dev.txt").write_text("pytest==7.0\n")
        files = DependencyFileDetector().detect(str(tmp_path))
        paths = [f.path for f in files]
        assert "requirements.txt" in paths
        assert "requirements-dev.txt" in paths

    def test_ignores_venv(self, tmp_path):
        venv = tmp_path / ".venv" / "lib"
        venv.mkdir(parents=True)
        (venv / "requirements.txt").write_text("ignored==1.0\n")
        (tmp_path / "requirements.txt").write_text("real==1.0\n")
        files = DependencyFileDetector().detect(str(tmp_path))
        assert len(files) == 1
        assert files[0].path == "requirements.txt"

    def test_empty_workspace(self, tmp_path):
        files = DependencyFileDetector().detect(str(tmp_path))
        assert files == []

    def test_nonexistent_workspace(self):
        files = DependencyFileDetector().detect("/nonexistent/path/xyz")
        assert files == []


# ══════════════════════════════════════════════════════════════════════════════
# 2. Python Parser
# ══════════════════════════════════════════════════════════════════════════════

class TestPythonParser:

    def test_pinned_version(self, tmp_path):
        f = tmp_path / "requirements.txt"
        f.write_text("Django==4.2.1\n")
        deps = parse_requirements_txt(str(f))
        assert len(deps) == 1
        assert deps[0].name == "Django"
        assert deps[0].current_version == "4.2.1"
        assert deps[0].version_constraint == "==4.2.1"

    def test_range_specifier(self, tmp_path):
        f = tmp_path / "requirements.txt"
        f.write_text("requests>=2.25,<3\n")
        deps = parse_requirements_txt(str(f))
        assert deps[0].current_version == "2.25"
        assert deps[0].version_constraint == ">=2.25,<3"


    def test_tilde_specifier(self, tmp_path):
        f = tmp_path / "requirements.txt"
        f.write_text("numpy~=1.21\n")
        deps = parse_requirements_txt(str(f))
        assert deps[0].name == "numpy"
        assert deps[0].version_constraint == "~=1.21"

    def test_extras_preserved(self, tmp_path):
        f = tmp_path / "requirements.txt"
        f.write_text("requests[security]==2.28.0\n")
        deps = parse_requirements_txt(str(f))
        assert deps[0].name == "requests"
        assert deps[0].extras == "[security]"
        assert deps[0].current_version == "2.28.0"

    def test_environment_marker(self, tmp_path):
        f = tmp_path / "requirements.txt"
        f.write_text('pywin32==306; sys_platform == "win32"\n')
        deps = parse_requirements_txt(str(f))
        assert deps[0].name == "pywin32"
        assert deps[0].environment_marker is not None

    def test_comments_skipped(self, tmp_path):
        f = tmp_path / "requirements.txt"
        f.write_text("# This is a comment\nDjango==4.2.1\n")
        deps = parse_requirements_txt(str(f))
        assert len(deps) == 1

    def test_blank_lines_skipped(self, tmp_path):
        f = tmp_path / "requirements.txt"
        f.write_text("\n\nDjango==4.2.1\n\n")
        deps = parse_requirements_txt(str(f))
        assert len(deps) == 1

    def test_multiple_dependencies(self, tmp_path):
        f = tmp_path / "requirements.txt"
        f.write_text("Django==4.2.1\nrequests==2.28.0\nnumpy~=1.21\n")
        deps = parse_requirements_txt(str(f))
        assert len(deps) == 3
        names = [d.name for d in deps]
        assert "Django" in names
        assert "requests" in names
        assert "numpy" in names

    def test_setup_cfg(self, tmp_path):
        f = tmp_path / "setup.cfg"
        f.write_text(textwrap.dedent("""\
            [options]
            install_requires =
                requests>=2.25
                Django==3.2
        """))
        deps = parse_setup_cfg(str(f))
        names = [d.name for d in deps]
        assert "requests" in names
        assert "Django" in names

    def test_pyproject_toml_pep621(self, tmp_path):
        f = tmp_path / "pyproject.toml"
        f.write_text(textwrap.dedent("""\
            [project]
            dependencies = [
                "Django>=3.2,<5",
                "requests==2.28.0",
            ]
        """))
        deps = parse_pyproject_toml(str(f))
        names = [d.name for d in deps]
        assert "Django" in names
        assert "requests" in names

    def test_invalid_file_returns_empty(self, tmp_path):
        f = tmp_path / "requirements.txt"
        f.write_text("\x00\x01\x02")   # binary garbage
        deps = parse_requirements_txt(str(f))
        # Should not raise; may return empty list
        assert isinstance(deps, list)


# ══════════════════════════════════════════════════════════════════════════════
# 3. Node Parser
# ══════════════════════════════════════════════════════════════════════════════

class TestNodeParser:

    def test_exact_version(self, tmp_path):
        f = tmp_path / "package.json"
        f.write_text(json.dumps({"dependencies": {"react": "18.2.0"}}))
        deps = parse_package_json(str(f))
        assert deps[0].name == "react"
        assert deps[0].current_version == "18.2.0"

    def test_caret_range(self, tmp_path):
        f = tmp_path / "package.json"
        f.write_text(json.dumps({"dependencies": {"react": "^18.2.0"}}))
        deps = parse_package_json(str(f))
        assert deps[0].current_version == "18.2.0"
        assert deps[0].version_constraint == "^18.2.0"


    def test_dev_dependencies_parsed(self, tmp_path):
        f = tmp_path / "package.json"
        f.write_text(json.dumps({
            "dependencies": {"react": "18.2.0"},
            "devDependencies": {"jest": "29.0.0"},
        }))
        deps = parse_package_json(str(f))
        names = [d.name for d in deps]
        assert "react" in names
        assert "jest" in names

    def test_invalid_json_returns_empty(self, tmp_path):
        f = tmp_path / "package.json"
        f.write_text("NOT JSON")
        deps = parse_package_json(str(f))
        assert deps == []


# ══════════════════════════════════════════════════════════════════════════════
# 4. Java Parser
# ══════════════════════════════════════════════════════════════════════════════

class TestJavaParser:

    def test_parse_dependency(self, tmp_path):
        f = tmp_path / "pom.xml"
        f.write_text(textwrap.dedent("""\
            <project>
              <dependencies>
                <dependency>
                  <groupId>org.springframework.boot</groupId>
                  <artifactId>spring-boot-starter</artifactId>
                  <version>2.7.0</version>
                </dependency>
              </dependencies>
            </project>
        """))
        deps = parse_pom_xml(str(f))
        assert len(deps) >= 1
        assert deps[0].name == "org.springframework.boot:spring-boot-starter"
        assert deps[0].current_version == "2.7.0"

    def test_property_placeholder_skipped(self, tmp_path):
        f = tmp_path / "pom.xml"
        f.write_text(textwrap.dedent("""\
            <project>
              <dependencies>
                <dependency>
                  <groupId>com.example</groupId>
                  <artifactId>my-lib</artifactId>
                  <version>${my.lib.version}</version>
                </dependency>
              </dependencies>
            </project>
        """))
        deps = parse_pom_xml(str(f))
        # current_version should be None for property placeholders
        assert all(d.current_version is None for d in deps)


# ══════════════════════════════════════════════════════════════════════════════
# 5. Pre-release Filtering
# ══════════════════════════════════════════════════════════════════════════════

class TestPreReleaseFiltering:

    @pytest.mark.parametrize("version,expected", [
        ("5.0.0",      True),
        ("1.2.3",      True),
        ("5.0.0a1",    False),
        ("5.0.0b2",    False),
        ("5.0.0rc1",   False),
        ("5.0.0.dev0", False),
        ("1.0.0alpha",  False),
        ("2.0-nightly", False),
        ("3.0-beta",    False),
        ("1.0.0pre1",   False),
    ])
    def test_stability_filter(self, version, expected):
        assert _is_stable(version) == expected


# ══════════════════════════════════════════════════════════════════════════════
# 6. Registry Client (mocked)
# ══════════════════════════════════════════════════════════════════════════════

class TestRegistryClient:

    def test_pypi_returns_latest_stable(self):
        mock_data = {
            "releases": {
                "4.2.0": [{"filename": "django-4.2.0.tar.gz"}],
                "5.0.0": [{"filename": "django-5.0.0.tar.gz"}],
                "5.1.0a1": [{"filename": "django-5.1.0a1.tar.gz"}],
            }
        }
        with patch("app.dependency_analysis.registry._http_get_json", return_value=mock_data):
            ver = get_latest_stable_version("Django", DependencyEcosystem.PYTHON)
        assert ver == "5.0.0"

    def test_pypi_filters_prerelease(self):
        mock_data = {
            "releases": {
                "4.0.0rc1": [{"filename": "f.tar.gz"}],
                "3.2.18":   [{"filename": "f.tar.gz"}],
            }
        }
        with patch("app.dependency_analysis.registry._http_get_json", return_value=mock_data):
            ver = get_latest_stable_version("Django", DependencyEcosystem.PYTHON)
        assert ver == "3.2.18"

    def test_pypi_returns_none_on_network_failure(self):
        with patch("app.dependency_analysis.registry._http_get_json", return_value=None):
            ver = get_latest_stable_version("requests", DependencyEcosystem.PYTHON)
        assert ver is None

    def test_npm_returns_latest_stable(self):
        mock_data = {
            "dist-tags": {"latest": "18.2.0"},
            "versions": {"18.2.0": {}, "19.0.0-alpha.1": {}},
        }
        with patch("app.dependency_analysis.registry._http_get_json", return_value=mock_data):
            ver = get_latest_stable_version("react", DependencyEcosystem.NODE)
        assert ver == "18.2.0"

    def test_npm_filters_prerelease_from_dist_tags(self):
        mock_data = {
            "dist-tags": {"latest": "19.0.0-rc.1"},
            "versions": {"18.2.0": {}, "19.0.0-rc.1": {}},
        }
        with patch("app.dependency_analysis.registry._http_get_json", return_value=mock_data):
            ver = get_latest_stable_version("react", DependencyEcosystem.NODE)
        # Should fall back to stable from versions list
        assert ver == "18.2.0"

    def test_maven_returns_latest_stable(self):
        mock_data = {
            "response": {
                "docs": [
                    {"v": "3.0.0"},
                    {"v": "2.7.18"},
                    {"v": "3.1.0-beta"},
                ]
            }
        }
        with patch("app.dependency_analysis.registry._http_get_json", return_value=mock_data):
            ver = get_latest_stable_version(
                "org.springframework.boot:spring-boot-starter",
                DependencyEcosystem.JAVA,
            )
        assert ver == "3.0.0"

    def test_unknown_ecosystem_returns_none(self):
        ver = get_latest_stable_version("something", DependencyEcosystem.UNKNOWN)
        assert ver is None


# ══════════════════════════════════════════════════════════════════════════════
# 7. Version Comparator
# ══════════════════════════════════════════════════════════════════════════════

class TestVersionComparator:

    def test_up_to_date(self):
        dep = _make_dep("django", "4.2.1", "4.2.1")
        compare_dependency(dep)
        assert dep.status == DependencyStatus.UP_TO_DATE
        assert not dep.update_required

    def test_update_available(self):
        dep = _make_dep("django", "3.2.18", "4.2.1")
        compare_dependency(dep)
        assert dep.status == DependencyStatus.UPDATE_AVAILABLE
        assert dep.update_required

    def test_lookup_failed_when_latest_none(self):
        dep = _make_dep("django", "3.2.18", None)
        compare_dependency(dep)
        assert dep.status == DependencyStatus.LOOKUP_FAILED
        assert not dep.update_required

    def test_constraint_blocked(self):
        dep = _make_dep("pandas", "1.5.3", "3.0.0", constraint=">=1.5,<3")
        compare_dependency(dep)
        assert dep.status == DependencyStatus.UPDATE_AVAILABLE
        assert dep.update_required

    def test_constraint_satisfied(self):
        dep = _make_dep("requests", "2.25.0", "2.31.0", constraint=">=2.25,<3")
        compare_dependency(dep)
        assert dep.status == DependencyStatus.UPDATE_AVAILABLE


    def test_invalid_version(self):
        dep = _make_dep("broken", "not-a-version-abc", "4.0.0")
        compare_dependency(dep)
        # Should not crash — returns INVALID_VERSION
        assert dep.status == DependencyStatus.INVALID_VERSION

    def test_semantic_ordering(self):
        """1.10 > 1.9 — must NOT use string comparison."""
        dep = _make_dep("lib", "1.9.0", "1.10.0")
        compare_dependency(dep)
        assert dep.status == DependencyStatus.UPDATE_AVAILABLE

    def test_no_version_pinned_no_constraint(self):
        dep = _make_dep("lib", None, "2.0.0", constraint=None)
        compare_dependency(dep)
        assert dep.status == DependencyStatus.UP_TO_DATE


# ══════════════════════════════════════════════════════════════════════════════
# 8. Requirement File Updater
# ══════════════════════════════════════════════════════════════════════════════

class TestUpdater:

    def _updated_dep(self, name: str, current: str, latest: str) -> Dependency:
        dep = _make_dep(name, current, latest)
        dep.status = DependencyStatus.UPDATE_AVAILABLE
        dep.update_required = True
        return dep

    def test_updates_pinned_version(self, tmp_path):
        f = tmp_path / "requirements.txt"
        f.write_text("Django==3.2.18\n")
        dep = self._updated_dep("Django", "3.2.18", "4.2.1")
        changed = update_requirements_txt(str(f), [dep])
        assert changed
        content = f.read_text()
        assert "Django==4.2.1" in content
        assert "3.2.18" not in content

    def test_preserves_comments(self, tmp_path):
        f = tmp_path / "requirements.txt"
        f.write_text("# Production dependencies\nDjango==3.2.18\n")
        dep = self._updated_dep("Django", "3.2.18", "4.2.1")
        update_requirements_txt(str(f), [dep])
        content = f.read_text()
        assert "# Production dependencies" in content

    def test_preserves_unrelated_deps(self, tmp_path):
        f = tmp_path / "requirements.txt"
        f.write_text("Django==3.2.18\nrequests==2.28.0\n")
        dep = self._updated_dep("Django", "3.2.18", "4.2.1")
        update_requirements_txt(str(f), [dep])
        content = f.read_text()
        assert "requests==2.28.0" in content

    def test_preserves_extras(self, tmp_path):
        f = tmp_path / "requirements.txt"
        f.write_text("requests[security]==2.28.0\n")
        dep = self._updated_dep("requests", "2.28.0", "2.31.0")
        update_requirements_txt(str(f), [dep])
        content = f.read_text()
        assert "requests[security]==2.31.0" in content

    def test_no_update_when_up_to_date(self, tmp_path):
        f = tmp_path / "requirements.txt"
        f.write_text("Django==4.2.1\n")
        dep = _make_dep("Django", "4.2.1", "4.2.1")
        dep.status = DependencyStatus.UP_TO_DATE
        dep.update_required = False
        changed = update_requirements_txt(str(f), [dep])
        assert not changed

    def test_lockfile_not_modified(self, tmp_path):
        """Lockfile protection: updater must not be called on lockfiles
        (the service layer ensures this, but the updater also returns False
        if no deps match)."""
        f = tmp_path / "Pipfile.lock"
        original = '{"default": {}}'
        f.write_text(original)
        dep = self._updated_dep("Django", "3.2", "4.2.1")
        # Calling updater directly on a lockfile — no match expected
        changed = update_requirements_txt(str(f), [dep])
        assert not changed or f.read_text() == original


# ══════════════════════════════════════════════════════════════════════════════
# 9. Validator
# ══════════════════════════════════════════════════════════════════════════════

class TestValidator:

    def test_valid_requirements(self, tmp_path):
        f = tmp_path / "requirements.txt"
        f.write_text("Django==4.2.1\nrequests>=2.28,<3\n")
        status, errors = validate_requirements_txt(str(f))
        assert status == ValidationStatus.PASSED
        assert errors == []

    def test_duplicate_dependency_flagged(self, tmp_path):
        f = tmp_path / "requirements.txt"
        f.write_text("Django==4.2.1\nDjango==3.2.18\n")
        status, errors = validate_requirements_txt(str(f))
        assert status == ValidationStatus.FAILED
        assert any("duplicate" in e.lower() for e in errors)

    def test_empty_file_passes(self, tmp_path):
        f = tmp_path / "requirements.txt"
        f.write_text("# only comments\n\n")
        status, errors = validate_requirements_txt(str(f))
        assert status == ValidationStatus.PASSED


# ══════════════════════════════════════════════════════════════════════════════
# 10. End-to-End Integration Test (mocked registry)
# ══════════════════════════════════════════════════════════════════════════════

class TestEndToEnd:
    """
    Simulates the full pipeline on a tiny synthetic project.
    Registry calls are mocked so no internet is required.
    """

    def _mock_registry(self, name: str, ecosystem: DependencyEcosystem) -> Optional[str]:
        versions = {
            "Django":   "5.0.3",
            "requests": "2.31.0",
            "numpy":    "1.26.4",
        }
        return versions.get(name)

    def test_full_pipeline(self, tmp_path):
        from app.dependency_analysis.service import DependencyAnalysisService

        # Create a synthetic project with an old dependency file
        req = tmp_path / "requirements.txt"
        req.write_text(textwrap.dedent("""\
            # Demo project
            Django==2.2.28
            requests==2.25.1
            numpy==1.21.0
        """))

        svc = DependencyAnalysisService()

        with patch(
            "app.dependency_analysis.service.get_latest_stable_version",
            side_effect=self._mock_registry,
        ):
            result = svc.analyze(str(tmp_path))

        # 1. Dependency files detected
        assert any(f.path == "requirements.txt" for f in result.dependency_files)

        # 2. Three dependencies parsed
        assert len(result.dependencies) == 3

        # 3. All three are outdated
        assert set(result.outdated) == {"Django", "requests", "numpy"}

        # 4. Proposed updates contain actual dynamically-resolved versions
        update_names = {u.dependency_name for u in result.proposed_updates}
        assert "Django" in update_names
        for update in result.proposed_updates:
            # Must NOT contain placeholder text
            assert update.proposed_version not in ("latest", "x.x.x", "...")
            assert update.proposed_version is not None

        # 5. requirements.txt was updated on disk
        assert "requirements.txt" in result.changed_files
        updated_content = req.read_text()
        assert "Django==5.0.3" in updated_content
        assert "requests==2.31.0" in updated_content
        assert "numpy==1.26.4" in updated_content

        # 6. Comments preserved
        assert "# Demo project" in updated_content

        # 7. Validation passed
        assert result.validation_status in (
            ValidationStatus.PASSED, ValidationStatus.SKIPPED
        )

    def test_lookup_failure_does_not_crash(self, tmp_path):
        from app.dependency_analysis.service import DependencyAnalysisService

        req = tmp_path / "requirements.txt"
        req.write_text("some-private-pkg==1.0.0\n")

        svc = DependencyAnalysisService()

        # Simulate complete registry failure
        with patch(
            "app.dependency_analysis.service.get_latest_stable_version",
            return_value=None,
        ):
            result = svc.analyze(str(tmp_path))

        assert "some-private-pkg" in result.lookup_failed
        assert result.changed_files == []   # nothing updated

    def test_constraint_blocked_upgraded(self, tmp_path):
        from app.dependency_analysis.service import DependencyAnalysisService

        req = tmp_path / "requirements.txt"
        req.write_text("pandas>=1.5,<3\n")

        svc = DependencyAnalysisService()

        with patch(
            "app.dependency_analysis.service.get_latest_stable_version",
            return_value="3.0.0",
        ):
            result = svc.analyze(str(tmp_path))

        assert "pandas" in result.outdated
        assert "requirements.txt" in result.changed_files
        # The range is upgraded to >=3.0.0
        assert "pandas>=3.0.0" in req.read_text()


    def test_lockfiles_never_modified(self, tmp_path):
        from app.dependency_analysis.service import DependencyAnalysisService

        lock = tmp_path / "package-lock.json"
        original = json.dumps({"lockfileVersion": 3})
        lock.write_text(original)

        svc = DependencyAnalysisService()
        with patch(
            "app.dependency_analysis.service.get_latest_stable_version",
            return_value="99.0.0",
        ):
            result = svc.analyze(str(tmp_path))

        # Lockfile must not appear in changed_files
        assert "package-lock.json" not in result.changed_files
        # Content must be byte-for-byte identical
        assert lock.read_text() == original
