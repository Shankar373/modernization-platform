"""
Migration Orchestrator — coordinates the full migration pipeline.

The orchestrator delegates all language-specific logic to adapters.
It does NOT contain language-specific if/elif routing.
"""
from __future__ import annotations

import json
import re
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

if not hasattr(CapabilityStatus, "PARTIALLY_AVAILABLE"):
    setattr(CapabilityStatus, "PARTIALLY_AVAILABLE", CapabilityStatus.PARTIAL)

# ── UniversalScanner C# Discovery Enhancements ──────────────────────────────
from app.discovery.scanner import _FRAMEWORK_SIGNATURES, _BUILD_SIGNATURES, _LANGUAGE_SIGNATURES
from app.core.domain.models import DetectedDependency

if "C#" in _LANGUAGE_SIGNATURES:
    _LANGUAGE_SIGNATURES["C#"]["marker_files"] = ["*.csproj", "*.sln"]


_CSHARP_FRAMEWORKS = [
    {"name": "ASP.NET MVC", "language": "C#", "markers": ["System.Web.Mvc", "Autofac.Mvc", "@Controller", "Global.asax", "routes.MapRoute"], "files": ["packages.config", "Web.config", "Global.asax", "*.csproj"]},
    {"name": "ASP.NET WebForms", "language": "C#", "markers": ["System.Web.UI", "Autofac.Web", ".aspx", "System.Web.Optimization"], "files": ["packages.config", "Web.config", "*.csproj"]},
    {"name": "ASP.NET Web API", "language": "C#", "markers": ["System.Web.Http", "ApiController", "Microsoft.AspNet.WebApi"], "files": ["packages.config", "Web.config", "*.csproj"]},
    {"name": "WCF", "language": "C#", "markers": ["System.ServiceModel", "ServiceContract", "OperationContract"], "files": ["packages.config", "Web.config", "*.csproj"]},
    {"name": "WinForms", "language": "C#", "markers": ["System.Windows.Forms", "Form"], "files": ["*.csproj", "*.cs"]},
    {"name": "WPF", "language": "C#", "markers": ["PresentationFramework", "System.Windows.Controls"], "files": ["*.csproj", "*.xaml"]},
    {"name": "Entity Framework", "language": "C#", "markers": ["EntityFramework", "DbContext"], "files": ["packages.config", "*.csproj", "Web.config", "App.config"]},
    {"name": "ASP.NET Core", "language": "C#", "markers": ["Microsoft.AspNetCore", "WebApplication.CreateBuilder"], "files": ["*.csproj", "Program.cs", "Startup.cs"]},
]

for fw in _CSHARP_FRAMEWORKS:
    if not any(f["name"] == fw["name"] for f in _FRAMEWORK_SIGNATURES):
        _FRAMEWORK_SIGNATURES.append(fw)

_CSHARP_BUILDS = [
    {"name": "MSBuild", "language": "C#", "files": ["*.sln", "*.csproj"]},
    {"name": "dotnet CLI", "language": "C#", "files": ["global.json"]},
]
for b in _CSHARP_BUILDS:
    if not any(b_sig["name"] == b["name"] for b_sig in _BUILD_SIGNATURES):
        _BUILD_SIGNATURES.append(b)

_orig_detect_version = UniversalScanner._detect_version

def _enhanced_detect_version(self, language: str, ws: Path):  # noqa: C901
    """Enhanced multi-language version detection. Falls back to original for unlisted languages."""
    try:
        if language == "C#":
            versions = set()
            for csproj in ws.rglob("*.csproj"):
                if self._is_ignored(csproj): continue
                try:
                    content = csproj.read_text(encoding="utf-8", errors="replace")
                    # <TargetFrameworkVersion>v4.7.2</TargetFrameworkVersion>
                    for v in re.findall(r"<TargetFrameworkVersion>\s*v?([\d\.]+)\s*</TargetFrameworkVersion>", content, re.IGNORECASE):
                        versions.add(f".NET Framework {v}")
                    # <TargetFramework>net461|net6.0|net8.0-windows</TargetFramework>
                    for tf in re.findall(r"<TargetFramework>\s*([a-zA-Z0-9\.\-]+)\s*</TargetFramework>", content, re.IGNORECASE):
                        tf_l = tf.lower()
                        if tf_l.startswith("netcoreapp"):
                            versions.add(f".NET Core {tf[10:]}")
                        elif tf_l.startswith("net") and len(tf_l) >= 4 and tf_l[3].isdigit():
                            suffix = tf[3:]
                            if "." in suffix or "-" in suffix:
                                major = suffix.split(".")[0]
                                versions.add(f".NET {suffix}" if int(major) >= 5 else f".NET Framework {suffix}")
                            else:
                                digits = list(suffix)
                                if len(digits) == 3:
                                    fmt = f"{digits[0]}.{digits[1]}.{digits[2]}"
                                elif len(digits) == 2:
                                    fmt = f"{digits[0]}.{digits[1]}"
                                else:
                                    fmt = ".".join(digits)
                                versions.add(f".NET {fmt}" if int(digits[0]) >= 5 else f".NET Framework {fmt}")
                        else:
                            versions.add(tf)
                except Exception:
                    pass
            if versions:
                def _cs_sort(v: str): return (0, v) if "Framework" in v else (1, v) if "Core" in v else (2, v)
                return ", ".join(sorted(versions, key=_cs_sort))

        elif language == "Java":
            # pom.xml — java.version, maven.compiler.source/release
            for pom in list(ws.rglob("pom.xml"))[:5]:
                if self._is_ignored(pom): continue
                try:
                    c = pom.read_text(encoding="utf-8", errors="replace")
                    for pat in [
                        r"<java\.version>(\d+(?:\.\d+)?)</java\.version>",
                        r"<maven\.compiler\.source>(\d+(?:\.\d+)?)</maven\.compiler\.source>",
                        r"<maven\.compiler\.release>(\d+)</maven\.compiler\.release>",
                        r"<source>(\d+(?:\.\d+)?)</source>",
                    ]:
                        m = re.search(pat, c)
                        if m:
                            return f"Java {m.group(1)}"
                except Exception:
                    pass
            # build.gradle / build.gradle.kts — sourceCompatibility, jvmTarget
            for grad in list(ws.rglob("build.gradle")) + list(ws.rglob("build.gradle.kts")):
                if self._is_ignored(grad): continue
                try:
                    c = grad.read_text(encoding="utf-8", errors="replace")
                    for pat in [
                        r"sourceCompatibility\s*=\s*['\"]?(\d+(?:\.\d+)?)['\"]?",
                        r"jvmTarget\s*=\s*['\"]([\d\.]+)['\"]?",
                        r"JavaVersion\.VERSION_(\d+)",
                    ]:
                        m = re.search(pat, c)
                        if m:
                            ver = m.group(1).replace("_", ".")
                            return f"Java {ver}"
                except Exception:
                    pass

        elif language == "Python":
            # runtime.txt → python-3.11.4  |  .python-version → 3.11
            for fname in ["runtime.txt", ".python-version"]:
                for p in [ws / fname] + list(ws.rglob(fname))[:3]:
                    if p.exists() and not self._is_ignored(p):
                        try:
                            raw = p.read_text(encoding="utf-8", errors="replace").strip()
                            m = re.search(r"python[-_ ]?([\d\.]+)", raw, re.IGNORECASE)
                            if m: return f"Python {m.group(1)}"
                            m = re.match(r"([\d\.]+)", raw)
                            if m: return f"Python {m.group(1)}"
                        except Exception:
                            pass
            # pyproject.toml — python_requires, target-version
            for pp in list(ws.rglob("pyproject.toml"))[:3]:
                if self._is_ignored(pp): continue
                try:
                    c = pp.read_text(encoding="utf-8", errors="replace")
                    m = re.search(r'python_requires\s*=\s*["\']>=?([\d\.]+)', c)
                    if m: return f"Python {m.group(1)}"
                    m = re.search(r'target-version\s*=\s*["\']py(\d)(\d+)', c)
                    if m: return f"Python {m.group(1)}.{m.group(2)}"
                    m = re.search(r'requires-python\s*=\s*["\']>=?([\d\.]+)', c)
                    if m: return f"Python {m.group(1)}"
                except Exception:
                    pass
            # setup.cfg
            for sc in list(ws.rglob("setup.cfg"))[:3]:
                if self._is_ignored(sc): continue
                try:
                    c = sc.read_text(encoding="utf-8", errors="replace")
                    m = re.search(r'python_requires\s*[=,]\s*>=?([\d\.]+)', c)
                    if m: return f"Python {m.group(1)}"
                except Exception:
                    pass

        elif language in ("JavaScript", "TypeScript"):
            # .nvmrc or .node-version
            for fname in [".nvmrc", ".node-version"]:
                p = ws / fname
                if p.exists():
                    try:
                        raw = p.read_text(encoding="utf-8", errors="replace").strip().lstrip("v")
                        if re.match(r"[\d\.]+", raw):
                            return f"Node {raw}"
                    except Exception:
                        pass
            # package.json engines.node
            for pkg in [ws / "package.json"] + list(ws.rglob("package.json"))[:3]:
                if pkg.exists() and not self._is_ignored(pkg):
                    try:
                        import json as _json
                        data = _json.loads(pkg.read_text(encoding="utf-8"))
                        node_ver = data.get("engines", {}).get("node")
                        if node_ver:
                            clean = re.sub(r"[^\d\.]", "", node_ver.split("||")[0].strip()).strip(".")
                            return f"Node {clean}" if clean else node_ver
                    except Exception:
                        pass
            # tsconfig.json compilerOptions.target
            if language == "TypeScript":
                for tsc in list(ws.rglob("tsconfig.json"))[:3]:
                    if self._is_ignored(tsc): continue
                    try:
                        import json as _json
                        data = _json.loads(tsc.read_text(encoding="utf-8"))
                        target = data.get("compilerOptions", {}).get("target", "")
                        if target:
                            return f"TypeScript / ES{target.replace('ES', '')}"
                    except Exception:
                        pass

        elif language == "Go":
            for gomod in list(ws.rglob("go.mod"))[:3]:
                if self._is_ignored(gomod): continue
                try:
                    c = gomod.read_text(encoding="utf-8", errors="replace")
                    m = re.search(r"^go\s+([\d\.]+)", c, re.MULTILINE)
                    if m: return f"Go {m.group(1)}"
                except Exception:
                    pass

        elif language == "PHP":
            for comp in list(ws.rglob("composer.json"))[:3]:
                if self._is_ignored(comp): continue
                try:
                    import json as _json
                    data = _json.loads(comp.read_text(encoding="utf-8"))
                    php_ver = data.get("require", {}).get("php", "")
                    if php_ver:
                        m = re.search(r"([\d\.]+)", php_ver)
                        if m: return f"PHP {m.group(1)}"
                except Exception:
                    pass

        elif language == "Ruby":
            # .ruby-version first
            rv = ws / ".ruby-version"
            if rv.exists():
                try:
                    raw = rv.read_text(encoding="utf-8", errors="replace").strip()
                    m = re.search(r"([\d\.]+)", raw)
                    if m: return f"Ruby {m.group(1)}"
                except Exception:
                    pass
            # Gemfile: ruby '3.2.0'
            gemfile = ws / "Gemfile"
            if gemfile.exists():
                try:
                    c = gemfile.read_text(encoding="utf-8", errors="replace")
                    m = re.search(r"ruby\s+['\"]([\d\.]+)['\"]", c)
                    if m: return f"Ruby {m.group(1)}"
                except Exception:
                    pass

        elif language in ("Kotlin",):
            for grad in list(ws.rglob("build.gradle.kts")) + list(ws.rglob("build.gradle")):
                if self._is_ignored(grad): continue
                try:
                    c = grad.read_text(encoding="utf-8", errors="replace")
                    m = re.search(r"jvmTarget\s*=\s*['\"]([\d\.]+)['\"]", c)
                    if m: return f"Kotlin / JVM {m.group(1)}"
                    # kotlin version in plugins block
                    m = re.search(r'kotlin\(["\']jvm["\']\)\s+version\s+["\']([\d\.]+)', c)
                    if m: return f"Kotlin {m.group(1)}"
                except Exception:
                    pass

    except Exception:
        pass
    return _orig_detect_version(self, language, ws)

UniversalScanner._detect_version = _enhanced_detect_version

_orig_detect_languages = UniversalScanner._detect_languages

def _enhanced_detect_languages(self, ws: Path, files: list[Path], ext_counts: dict):
    detected = _orig_detect_languages(self, ws, files, ext_counts)

    # Enrich version for every detected language using enhanced version detection
    for lang in detected:
        if not lang.version:
            lang.version = self._detect_version(lang.name, ws)

    # C# special case — ensure it appears even if the base scanner missed it
    has_cs = any(f.suffix.lower() == ".cs" for f in files)
    has_proj = any(f.suffix.lower() in (".csproj", ".sln") for f in ws.rglob("*") if not self._is_ignored(f))
    cs_lang = next((l for l in detected if l.name == "C#"), None)
    if not cs_lang and (has_cs or has_proj):
        from app.core.domain.models import DetectedLanguage, DetectionEvidence
        ver = self._detect_version("C#", ws)
        detected.append(DetectedLanguage(
            name="C#",
            version=ver,
            confidence=0.9,
            evidence=[DetectionEvidence(description="Found C# source/project files", weight=0.9)],
        ))

    return detected

UniversalScanner._detect_languages = _enhanced_detect_languages



_orig_detect_dependencies = UniversalScanner._detect_dependencies

def _enhanced_detect_dependencies(self, ws: Path):  # noqa: C901
    # Start with original base scanner dependencies (Java pom.xml & Python requirements.txt)
    base_deps = _orig_detect_dependencies(self, ws)
    
    seen = set()
    deps = []
    
    def add_dep(name: str, version: Optional[str], lang: str):
        if not name:
            return
        name = name.strip()
        version = version.strip() if version else None
        key = (name.lower(), lang.lower())
        if key not in seen:
            seen.add(key)
            deps.append(DetectedDependency(name=name, version=version, language=lang))

    # Add base dependencies first (and normalize their names/versions)
    for d in base_deps:
        add_dep(d.name, d.version, d.language)

    # 1. C# packages.config
    for pkg_file in ws.rglob("packages.config"):
        if self._is_ignored(pkg_file): continue
        try:
            content = pkg_file.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r'<package\s+([^>]+?)/?>', content, re.IGNORECASE):
                attrs = dict(re.findall(r'(\w+)\s*=\s*[\'"]([^\'"]+)[\'"]', m.group(1)))
                name = attrs.get("id")
                version = attrs.get("version")
                if name:
                    add_dep(name, version, "C#")
        except Exception:
            pass

    # 2. C# PackageReference (.csproj)
    for csproj in ws.rglob("*.csproj"):
        if self._is_ignored(csproj): continue
        try:
            content = csproj.read_text(encoding="utf-8", errors="replace")
            # Parse PackageReference block tags and self-closing tags
            matches = re.finditer(r'<PackageReference\s+([^>]+?)(?:/>|>(.*?)</PackageReference>)', content, re.DOTALL | re.IGNORECASE)
            for m in matches:
                attrs_str = m.group(1)
                inner_content = m.group(2) if m.group(2) else ""
                attrs = dict(re.findall(r'(\w+)\s*=\s*[\'"]([^\'"]+)[\'"]', attrs_str))
                name = attrs.get("Include") or attrs.get("Update")
                if not name:
                    continue
                version = attrs.get("Version")
                if not version and inner_content:
                    v_match = re.search(r'<Version>\s*(.*?)\s*</Version>', inner_content, re.IGNORECASE)
                    if v_match:
                        version = v_match.group(1).strip()
                add_dep(name, version, "C#")
        except Exception:
            pass

    # 3. JavaScript / TypeScript package.json
    for pkg_file in ws.rglob("package.json"):
        if self._is_ignored(pkg_file): continue
        try:
            import json as _json
            data = _json.loads(pkg_file.read_text(encoding="utf-8", errors="replace"))
            for dep_type in ["dependencies", "devDependencies"]:
                for name, ver in data.get(dep_type, {}).items():
                    clean_ver = re.sub(r'^[~^>=<*\s]+', '', str(ver)).strip()
                    add_dep(name, clean_ver or None, "JavaScript")
        except Exception:
            pass

    # 4. Ruby Gemfile & Gemfile.lock
    for gfl in ws.rglob("Gemfile.lock"):
        if self._is_ignored(gfl): continue
        try:
            content = gfl.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r'^\s{4}([a-zA-Z0-9_\-]+)\s+\(([\d\.]+)\)', content, re.MULTILINE):
                add_dep(m.group(1), m.group(2), "Ruby")
        except Exception:
            pass
    for gf in ws.rglob("Gemfile"):
        if self._is_ignored(gf): continue
        try:
            content = gf.read_text(encoding="utf-8", errors="replace")
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("gem "):
                    m = re.match(r"gem\s+['\"]([^'\"]+)['\"](?:\s*,\s*['\"]([^'\"]+)['\"])?", line)
                    if m:
                        name = m.group(1)
                        version = m.group(2)
                        if version:
                            version = re.sub(r'^[~^>=<*\s]+', '', version).strip()
                        add_dep(name, version or None, "Ruby")
        except Exception:
            pass

    # 5. Python pyproject.toml
    for ppt in ws.rglob("pyproject.toml"):
        if self._is_ignored(ppt): continue
        try:
            content = ppt.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r'["\']?([a-zA-Z0-9_\-]+)["\']?\s*=\s*["\']([^"\']+)["\']', content):
                name, ver = m.group(1), m.group(2)
                if name not in ("python", "target-version", "requires-python"):
                    clean_ver = re.sub(r'^[~^>=<*\s]+', '', ver).strip()
                    add_dep(name, clean_ver or None, "Python")
        except Exception:
            pass

    # 6. Go go.mod
    for gm in ws.rglob("go.mod"):
        if self._is_ignored(gm): continue
        try:
            content = gm.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r'^\s*([a-zA-Z0-9\.\-_/]+)\s+(v[\d\.]+)', content, re.MULTILINE):
                add_dep(m.group(1), m.group(2).lstrip("v"), "Go")
        except Exception:
            pass

    # 7. PHP composer.json
    for comp in ws.rglob("composer.json"):
        if self._is_ignored(comp): continue
        try:
            import json as _json
            data = _json.loads(comp.read_text(encoding="utf-8", errors="replace"))
            for dep_type in ["require", "require-dev"]:
                for name, ver in data.get(dep_type, {}).items():
                    if name.lower() != "php":
                        clean_ver = re.sub(r'^[~^>=<*\s]+', '', str(ver)).strip()
                        add_dep(name, clean_ver or None, "PHP")
        except Exception:
            pass

    # 8. Gradle build files (Java / Kotlin)
    for grad in list(ws.rglob("build.gradle")) + list(ws.rglob("build.gradle.kts")):
        if self._is_ignored(grad): continue
        try:
            content = grad.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r'(?:implementation|api|compile|testImplementation)\s*\(?["\']([^"\':]+):([^"\':]+):([^"\':]+)["\']\)?', content):
                add_dep(f"{m.group(1)}:{m.group(2)}", m.group(3), "Java")
        except Exception:
            pass

    return deps[:150]


UniversalScanner._detect_dependencies = _enhanced_detect_dependencies

_orig_detect_testing = UniversalScanner._detect_testing_frameworks

# All source/test file extensions across enterprise languages the user listed
_ALL_SOURCE_EXTENSIONS = frozenset({
    # JVM
    ".java", ".kt", ".kts", ".groovy", ".scala",
    # .NET
    ".cs", ".fs", ".fsx", ".vb", ".vbs",
    # Web
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    # Native
    ".cpp", ".cc", ".cxx", ".h", ".hpp", ".c",
    # Systems
    ".go", ".rs",
    # Scripting / Dynamic
    ".py", ".rb", ".php", ".lua", ".r", ".R",
    # Mobile / Cross-platform
    ".swift", ".m", ".mm", ".dart",
    # Shell / Infra
    ".sh", ".bash", ".ps1",
    # Functional
    ".ex", ".exs", ".erl", ".hrl", ".hs", ".lhs", ".clj", ".cljs",
    # Data / Config
    ".sql",
    # Build/config files that contain test deps
    ".csproj", ".config",
})

# Per-language test framework signatures: {framework_name: [markers...]}
# Markers are matched case-insensitively against source file content
_TEST_FRAMEWORK_SIGNATURES: dict[str, list[str]] = {
    # C# / .NET
    "MSTest":           ["microsoft.visualstudio.testtools.unittesting", "[testclass]", "[testmethod]", "mstest.testframework"],
    "NUnit":            ["nunit.framework", "[testfixture]", "[test]", "nunit"],
    "xUnit":            ["xunit", "[fact]", "[theory]", "xunit.core"],
    # Java / Kotlin
    "JUnit 5":          ["org.junit.jupiter", "@test", "junit.jupiter", "@extendwith"],
    "JUnit 4":          ["org.junit.test", "import org.junit;", "junit:junit"],
    "TestNG":           ["org.testng", "testng", "@test", "testng.annotations"],
    "Mockito":          ["mockito", "@mock", "@injectmocks", "mockito-core"],
    "Spock":            ["spock.lang", "spockframework", "def \"should "],
    "Kotest":           ["io.kotest", "kotest-runner", "shouldbe", "describe {"],
    # Python
    "pytest":           ["import pytest", "from pytest", "@pytest.fixture", "def test_", "pytest"],
    "unittest":         ["import unittest", "testcase", "unittest.main"],
    "nose2":            ["nose2", "import nose"],
    # JavaScript / TypeScript
    "Jest":             ["jest", "describe(", "it(", "test(", "expect(", "beforeeach", "aftereach"],
    "Vitest":           ["vitest", "from 'vitest'", "from \"vitest\""],
    "Mocha":            ["mocha", "describe(", "it(", "before(", "after("],
    "Jasmine":          ["jasmine", "describe(", "it(", "expect("],
    "Cypress":          ["cypress", "cy.visit", "cy.get", "cy."],
    "Playwright":       ["@playwright/test", "test.describe", "page.goto"],
    # Go
    "Go test":          ["testing.t", "func test", "t.run(", "testmain"],
    # PHP
    "PHPUnit":          ["phpunit", "use phpunit", "extends testcase", "@test"],
    # Ruby
    "RSpec":            ["rspec", "describe ", "it \"should", "expect("],
    "Minitest":         ["minitest", "test_", "assert_equal"],
    # Rust
    "Rust test":        ["#[test]", "#[cfg(test)]", "mod tests {"],
    # Swift
    "XCTest":           ["xctest", "func test", "xctassert"],
    # C / C++
    "Google Test":      ["gtest", "googletest", "test_f(", "test_p(", "expect_eq"],
    "Catch2":           ["catch2", "require(", "test_case(", "section("],
    # Elixir
    "ExUnit":           ["exunit", "use exunit.case", "defmodule", "test \""],
    # Haskell
    "HUnit":            ["hunit", "test.hunit", "testcase", "assertequal"],
    "QuickCheck":       ["quickcheck", "prop_", "arbitrary"],
    # Clojure
    "clojure.test":     ["clojure.test", "deftest", "is (", "testing \""],
    # Scala
    "ScalaTest":        ["scalatest", "funsuite", "flatspec", "behavior of"],
    # Dart / Flutter
    "Flutter test":     ["flutter_test", "testwidgets", "expect(", "group("],
    # Shell
    "Bats":             ["bats", "@test", "load 'test_helper'"],
}

# Manifest files that declare test deps (by language)
_TEST_MANIFEST_CHECKS: list[tuple[str, str, str]] = [
    # (glob, framework_name, marker_string)
    ("packages.config",     "MSTest",   "mstest"),
    ("packages.config",     "NUnit",    "nunit"),
    ("packages.config",     "xUnit",    "xunit"),
    ("*.csproj",             "MSTest",   "mstest"),
    ("*.csproj",             "NUnit",    "nunit"),
    ("*.csproj",             "xUnit",    "xunit"),
    ("pom.xml",              "JUnit 5",  "junit-jupiter"),
    ("pom.xml",              "JUnit 4",  "junit:junit"),
    ("pom.xml",              "TestNG",   "testng"),
    ("pom.xml",              "Mockito",  "mockito"),
    ("build.gradle",         "JUnit 5",  "junit-jupiter"),
    ("build.gradle",         "JUnit 4",  "junit:junit"),
    ("build.gradle",         "TestNG",   "testng"),
    ("build.gradle",         "Kotest",   "kotest"),
    ("build.gradle.kts",     "JUnit 5",  "junit-jupiter"),
    ("build.gradle.kts",     "Kotest",   "kotest"),
    ("package.json",         "Jest",     "jest"),
    ("package.json",         "Vitest",   "vitest"),
    ("package.json",         "Mocha",    "mocha"),
    ("package.json",         "Jasmine",  "jasmine"),
    ("package.json",         "Cypress",  "cypress"),
    ("package.json",         "Playwright", "@playwright/test"),
    ("requirements*.txt",    "pytest",   "pytest"),
    ("requirements*.txt",    "unittest", "unittest"),
    ("pyproject.toml",       "pytest",   "pytest"),
    ("pyproject.toml",       "unittest", "unittest"),
    ("Gemfile",              "RSpec",    "rspec"),
    ("Gemfile",              "Minitest", "minitest"),
    ("composer.json",        "PHPUnit",  "phpunit"),
    ("Cargo.toml",           "Rust test", "[dev-dependencies]"),
    ("go.mod",               "Go test",  "testing"),
]

def _enhanced_detect_testing(self, ws: Path, files: list[Path]):
    found: list[str] = _orig_detect_testing(self, ws, files)
    found_set: set[str] = set(found)

    # ── Pass 1: Scan manifest / project files for test package references ─────
    for glob_pat, fw_name, marker in _TEST_MANIFEST_CHECKS:
        if fw_name in found_set:
            continue
        for mfile in ws.rglob(glob_pat):
            if self._is_ignored(mfile):
                continue
            try:
                content = mfile.read_text(encoding="utf-8", errors="replace").lower()
                if marker.lower() in content:
                    found.append(fw_name)
                    found_set.add(fw_name)
                    break
            except Exception:
                pass

    # ── Pass 2: Scan TEST-SPECIFIC source files for annotations/imports ────────
    # Only files that are plausibly test files (by name or directory) to avoid
    # false positives from app code containing describe/expect/it patterns.
    _TEST_DIR_PARTS = frozenset({
        "test", "tests", "spec", "specs", "__tests__", "__test__",
        "unittest", "unittests", "integration", "e2e", "acceptance",
    })
    _TEST_FILE_PATTERNS = frozenset({
        "test_", "_test.", ".test.", ".spec.", "_spec.",
        "test.", "spec.", "tests.",
    })

    def _is_test_file(p: Path) -> bool:
        # Check if any directory part is a known test directory
        for part in p.parts:
            if part.lower() in _TEST_DIR_PARTS:
                return True
        # Check filename patterns (prefix/suffix style: test_foo.py, foo_test.go)
        name_lower = p.name.lower()
        if any(pat in name_lower for pat in _TEST_FILE_PATTERNS):
            return True
        # Check if the file stem CONTAINS the word "test" or "spec" as a word
        # Covers: UnitTest1.cs, MyTests.java, FooSpec.rb, TestHelper.js
        stem_lower = p.stem.lower()
        if "test" in stem_lower or "spec" in stem_lower:
            return True
        return False


    source_chunks: list[str] = []
    total_chars = 0
    max_total = 4_000_000   # 4 MB total cap
    per_file_cap = 8_000    # 8 KB per file

    for f in files:
        if total_chars >= max_total:
            break
        if f.suffix.lower() not in _ALL_SOURCE_EXTENSIONS:
            continue
        if not _is_test_file(f):
            continue  # Skip non-test files to avoid false positives
        try:
            chunk = f.read_text(encoding="utf-8", errors="replace")[:per_file_cap]
            source_chunks.append(chunk)
            total_chars += len(chunk)
        except Exception:
            pass

    all_text_lower = "\n".join(source_chunks).lower()

    for fw_name, markers in _TEST_FRAMEWORK_SIGNATURES.items():
        if fw_name in found_set:
            continue
        if any(m.lower() in all_text_lower for m in markers):
            found.append(fw_name)
            found_set.add(fw_name)

    return found

UniversalScanner._detect_testing_frameworks = _enhanced_detect_testing





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
        """Route to adapter by targets[0].language; fall back to steps[0].adapter."""
        if not plan:
            return None
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
