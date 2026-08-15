"""
Universal Codebase Scanner — technology discovery engine.

Detects programming languages, versions, frameworks, build systems,
dependencies, databases, testing frameworks, and frontend technologies.

All detections include confidence scores and evidence lists.
Detection is never claimed to be perfect.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from app.core.domain.models import (
    DetectedBuildSystem,
    DetectedDependency,
    DetectedFramework,
    DetectedLanguage,
    DetectionEvidence,
    TechnologyProfile,
    DocItem,
    DetectedDocumentation,
)


# ── Language Signatures ───────────────────────────────────────────────────────

_LANGUAGE_SIGNATURES: Dict[str, dict] = {
    "Java": {
        "extensions": [".java"],
        "marker_files": ["pom.xml", "build.gradle", "build.gradle.kts"],
        "content_patterns": [r"public\s+class\s+\w+", r"import\s+java\."],
    },
    "Python": {
        "extensions": [".py"],
        "marker_files": ["pyproject.toml", "requirements.txt", "setup.py", "Pipfile"],
        "content_patterns": [r"^import\s+\w+", r"^from\s+\w+\s+import"],
    },
    "JavaScript": {
        "extensions": [".js", ".mjs", ".cjs"],
        "marker_files": ["package.json"],
        "content_patterns": [r"require\(", r"module\.exports", r"const\s+\w+\s*="],
    },
    "TypeScript": {
        "extensions": [".ts", ".tsx"],
        "marker_files": ["tsconfig.json"],
        "content_patterns": [r":\s*string", r":\s*number", r"interface\s+\w+"],
    },
    "Go": {
        "extensions": [".go"],
        "marker_files": ["go.mod", "go.sum"],
        "content_patterns": [r"^package\s+\w+", r"^import\s+\("],
    },
    "C": {
        "extensions": [".c", ".h"],
        "marker_files": ["CMakeLists.txt", "Makefile"],
        "content_patterns": [r"#include\s+<", r"int\s+main\("],
    },
    "C++": {
        "extensions": [".cpp", ".cxx", ".cc", ".hpp"],
        "marker_files": ["CMakeLists.txt"],
        "content_patterns": [r"#include\s+<iostream>", r"std::"],
    },
    "C#": {
        "extensions": [".cs"],
        "marker_files": ["*.csproj", "*.sln"],
        "content_patterns": [r"using\s+System", r"namespace\s+\w+"],
    },
    "PHP": {
        "extensions": [".php"],
        "marker_files": ["composer.json"],
        "content_patterns": [r"<\?php", r"namespace\s+\w+"],
    },
    "Ruby": {
        "extensions": [".rb"],
        "marker_files": ["Gemfile", "Rakefile"],
        "content_patterns": [r"^require\s+", r"def\s+\w+"],
    },
    "COBOL": {
        "extensions": [".cob", ".cbl", ".cobol"],
        "marker_files": [],
        "content_patterns": [r"IDENTIFICATION DIVISION", r"PROCEDURE DIVISION"],
    },
    "HTML": {
        "extensions": [".html", ".htm"],
        "marker_files": [],
        "content_patterns": [r"<!DOCTYPE html>", r"<html"],
    },
    "CSS": {
        "extensions": [".css", ".scss", ".sass", ".less"],
        "marker_files": [],
        "content_patterns": [],
    },
    "Kotlin": {
        "extensions": [".kt", ".kts"],
        "marker_files": ["build.gradle.kts"],
        "content_patterns": [r"fun\s+\w+\(", r"^import\s+kotlin\."],
    },
}

# ── Framework Signatures ──────────────────────────────────────────────────────

_FRAMEWORK_SIGNATURES: List[dict] = [
    {"name": "Spring Boot", "language": "Java", "markers": ["spring-boot-starter", "SpringApplication"], "files": ["pom.xml", "build.gradle"]},
    {"name": "Spring MVC", "language": "Java", "markers": ["spring-webmvc", "@Controller"], "files": ["pom.xml"]},
    {"name": "Django", "language": "Python", "markers": ["django", "INSTALLED_APPS"], "files": ["requirements.txt", "pyproject.toml", "manage.py"]},
    {"name": "Flask", "language": "Python", "markers": ["flask", "from flask import"], "files": ["requirements.txt", "pyproject.toml"]},
    {"name": "FastAPI", "language": "Python", "markers": ["fastapi", "from fastapi import"], "files": ["requirements.txt", "pyproject.toml"]},
    {"name": "React", "language": "JavaScript", "markers": ["react", "react-dom"], "files": ["package.json"]},
    {"name": "Vue.js", "language": "JavaScript", "markers": ["vue"], "files": ["package.json"]},
    {"name": "Angular", "language": "TypeScript", "markers": ["@angular/core"], "files": ["package.json"]},
    {"name": "Next.js", "language": "JavaScript", "markers": ["next"], "files": ["package.json"]},
    {"name": "Laravel", "language": "PHP", "markers": ["laravel/framework"], "files": ["composer.json"]},
    {"name": "Ruby on Rails", "language": "Ruby", "markers": ["rails"], "files": ["Gemfile"]},
]

_BUILD_SIGNATURES: List[dict] = [
    {"name": "Maven", "language": "Java", "files": ["pom.xml"]},
    {"name": "Gradle", "language": "Java", "files": ["build.gradle", "build.gradle.kts", "gradlew"]},
    {"name": "pip", "language": "Python", "files": ["requirements.txt", "setup.py"]},
    {"name": "Poetry", "language": "Python", "files": ["pyproject.toml", "poetry.lock"]},
    {"name": "npm", "language": "JavaScript", "files": ["package.json", "package-lock.json"]},
    {"name": "yarn", "language": "JavaScript", "files": ["yarn.lock"]},
    {"name": "pnpm", "language": "JavaScript", "files": ["pnpm-lock.yaml"]},
    {"name": "Go modules", "language": "Go", "files": ["go.mod"]},
    {"name": "Cargo", "language": "Rust", "files": ["Cargo.toml"]},
    {"name": "CMake", "language": "C/C++", "files": ["CMakeLists.txt"]},
    {"name": "Composer", "language": "PHP", "files": ["composer.json"]},
    {"name": "Bundler", "language": "Ruby", "files": ["Gemfile"]},
    {"name": "MSBuild", "language": "C#", "files": ["*.sln", "*.csproj"]},
    {"name": "dotnet CLI", "language": "C#", "files": ["global.json"]},
]

_CSHARP_FRAMEWORKS: List[dict] = [
    {"name": "ASP.NET MVC", "language": "C#", "markers": ["System.Web.Mvc", "Autofac.Mvc", "@Controller", "Global.asax", "routes.MapRoute"], "files": ["packages.config", "Web.config", "Global.asax", "*.csproj"]},
    {"name": "ASP.NET WebForms", "language": "C#", "markers": ["System.Web.UI", "Autofac.Web", ".aspx", "System.Web.Optimization"], "files": ["packages.config", "Web.config", "*.csproj"]},
    {"name": "ASP.NET Web API", "language": "C#", "markers": ["System.Web.Http", "ApiController", "Microsoft.AspNet.WebApi"], "files": ["packages.config", "Web.config", "*.csproj"]},
    {"name": "WCF", "language": "C#", "markers": ["System.ServiceModel", "ServiceContract", "OperationContract"], "files": ["packages.config", "Web.config", "*.csproj"]},
    {"name": "WinForms", "language": "C#", "markers": ["System.Windows.Forms", "Form"], "files": ["*.csproj", "*.cs"]},
    {"name": "WPF", "language": "C#", "markers": ["PresentationFramework", "System.Windows.Controls"], "files": ["*.csproj", "*.xaml"]},
    {"name": "Entity Framework", "language": "C#", "markers": ["EntityFramework", "DbContext"], "files": ["packages.config", "*.csproj", "Web.config", "App.config"]},
    {"name": "ASP.NET Core", "language": "C#", "markers": ["Microsoft.AspNetCore", "WebApplication.CreateBuilder"], "files": ["*.csproj", "Program.cs", "Startup.cs"]},
]
for _fw in _CSHARP_FRAMEWORKS:
    if not any(f["name"] == _fw["name"] for f in _FRAMEWORK_SIGNATURES):
        _FRAMEWORK_SIGNATURES.append(_fw)


# ── Test framework signatures (enhanced) ──────────────────────────────────────

_ALL_SOURCE_EXTENSIONS = frozenset({
    ".java", ".kt", ".kts", ".groovy", ".scala",
    ".cs", ".fs", ".fsx", ".vb", ".vbs",
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".cpp", ".cc", ".cxx", ".h", ".hpp", ".c",
    ".go", ".rs",
    ".py", ".rb", ".php", ".lua", ".r", ".R",
    ".swift", ".m", ".mm", ".dart",
    ".sh", ".bash", ".ps1",
    ".ex", ".exs", ".erl", ".hrl", ".hs", ".lhs", ".clj", ".cljs",
    ".sql",
    ".csproj", ".config",
})

_TEST_FRAMEWORK_SIGNATURES: dict[str, list[str]] = {
    "MSTest":           ["microsoft.visualstudio.testtools.unittesting", "[testclass]", "[testmethod]", "mstest.testframework"],
    "NUnit":            ["nunit.framework", "[testfixture]", "[test]", "nunit"],
    "xUnit":            ["xunit", "[fact]", "[theory]", "xunit.core"],
    "JUnit 5":          ["org.junit.jupiter", "@test", "junit.jupiter", "@extendwith"],
    "JUnit 4":          ["org.junit.test", "import org.junit;", "junit:junit"],
    "TestNG":           ["org.testng", "testng", "@test", "testng.annotations"],
    "Mockito":          ["mockito", "@mock", "@injectmocks", "mockito-core"],
    "Spock":            ["spock.lang", "spockframework", "def \"should "],
    "Kotest":           ["io.kotest", "kotest-runner", "shouldbe", "describe {"],
    "pytest":           ["import pytest", "from pytest", "@pytest.fixture", "def test_", "pytest"],
    "unittest":         ["import unittest", "testcase", "unittest.main"],
    "nose2":            ["nose2", "import nose"],
    "Jest":             ["jest", "describe(", "it(", "test(", "expect(", "beforeeach", "aftereach"],
    "Vitest":           ["vitest", "from 'vitest'", "from \"vitest\""],
    "Mocha":            ["mocha", "describe(", "it(", "before(", "after("],
    "Jasmine":          ["jasmine", "describe(", "it(", "expect("],
    "Cypress":          ["cypress", "cy.visit", "cy.get", "cy."],
    "Playwright":       ["@playwright/test", "test.describe", "page.goto"],
    "Go test":          ["testing.t", "func test", "t.run(", "testmain"],
    "PHPUnit":          ["phpunit", "use phpunit", "extends testcase", "@test"],
    "RSpec":            ["rspec", "describe ", "it \"should", "expect("],
    "Minitest":         ["minitest", "test_", "assert_equal"],
    "Rust test":        ["#[test]", "#[cfg(test)]", "mod tests {"],
    "XCTest":           ["xctest", "func test", "xctassert"],
    "Google Test":      ["gtest", "googletest", "test_f(", "test_p(", "expect_eq"],
    "Catch2":           ["catch2", "require(", "test_case(", "section("],
    "ExUnit":           ["exunit", "use exunit.case", "defmodule", "test \""],
    "HUnit":            ["hunit", "test.hunit", "testcase", "assertequal"],
    "QuickCheck":       ["quickcheck", "prop_", "arbitrary"],
    "clojure.test":     ["clojure.test", "deftest", "is (", "testing \""],
    "ScalaTest":        ["scalatest", "funsuite", "flatspec", "behavior of"],
    "Flutter test":     ["flutter_test", "testwidgets", "expect(", "group("],
    "Bats":             ["bats", "@test", "load 'test_helper'"],
}

_TEST_MANIFEST_CHECKS: List[tuple] = [
    ("packages.config",     "MSTest",   "mstest"),
    ("packages.config",     "NUnit",    "nunit"),
    ("packages.config",     "xUnit",    "xunit"),
    ("*.csproj",            "MSTest",   "mstest"),
    ("*.csproj",            "NUnit",    "nunit"),
    ("*.csproj",            "xUnit",    "xunit"),
    ("pom.xml",             "JUnit 5",  "junit-jupiter"),
    ("pom.xml",             "JUnit 4",  "junit:junit"),
    ("pom.xml",             "TestNG",   "testng"),
    ("pom.xml",             "Mockito",  "mockito"),
    ("build.gradle",        "JUnit 5",  "junit-jupiter"),
    ("build.gradle",        "JUnit 4",  "junit:junit"),
    ("build.gradle",        "TestNG",   "testng"),
    ("build.gradle",        "Kotest",   "kotest"),
    ("build.gradle.kts",    "JUnit 5",  "junit-jupiter"),
    ("build.gradle.kts",    "Kotest",   "kotest"),
    ("package.json",        "Jest",     "jest"),
    ("package.json",        "Vitest",   "vitest"),
    ("package.json",        "Mocha",    "mocha"),
    ("package.json",        "Jasmine",  "jasmine"),
    ("package.json",        "Cypress",  "cypress"),
    ("package.json",        "Playwright", "@playwright/test"),
    ("requirements*.txt",   "pytest",   "pytest"),
    ("requirements*.txt",   "unittest", "unittest"),
    ("pyproject.toml",      "pytest",   "pytest"),
    ("pyproject.toml",      "unittest", "unittest"),
    ("Gemfile",             "RSpec",    "rspec"),
    ("Gemfile",             "Minitest", "minitest"),
    ("composer.json",       "PHPUnit",  "phpunit"),
    ("Cargo.toml",          "Rust test", "[dev-dependencies]"),
    ("go.mod",              "Go test",  "testing"),
]


class UniversalScanner:
    """
    Scans a repository and produces a TechnologyProfile with confidence scores.

    Detection is never claimed to be perfect — all results include
    confidence scores (0.0–1.0) and supporting evidence.
    """

    def scan(self, workspace_path: str) -> TechnologyProfile:
        ws = Path(workspace_path)
        if not ws.exists():
            return TechnologyProfile()

        # Index all files
        all_files = list(ws.rglob("*"))
        files = [f for f in all_files if f.is_file() and not self._is_ignored(f)]

        file_count = len(files)
        ext_counts: Dict[str, int] = {}
        for f in files:
            ext = f.suffix.lower()
            if ext:
                ext_counts[ext] = ext_counts.get(ext, 0) + 1

        profile = TechnologyProfile(
            file_count=file_count,
        )

        profile.languages = self._detect_languages(ws, files, ext_counts)
        profile.frameworks = self._detect_frameworks(ws, files)
        profile.build_systems = self._detect_build_systems(ws, files)
        profile.dependencies = self._detect_dependencies(ws)
        profile.testing_frameworks = self._detect_testing_frameworks(ws, files)
        profile.databases = self._detect_databases(ws, files)
        profile.frontend_technologies = self._detect_frontend(ws, files)
        profile.documentation = self._scan_documentation(ws, files)
        profile.is_multi_language = len(profile.languages) > 1

        return profile

    def _is_ignored(self, f: Path) -> bool:
        ignore_dirs = {".git", "node_modules", ".venv", "venv", "__pycache__", ".idea", "target", "build", "dist", "site-packages", "vendor", ".pytest_cache", ".next"}
        for p in f.parts:
            pl = p.lower()
            if pl in ignore_dirs or pl.startswith(".venv") or "venv" in pl or "site-packages" in pl:
                return True
        return False


    def _detect_languages(self, ws: Path, files: List[Path], ext_counts: Dict[str, int]) -> List[DetectedLanguage]:
        detected = []
        for lang, sig in _LANGUAGE_SIGNATURES.items():
            evidence = []
            score = 0.0

            # Extension evidence
            ext_hits = sum(ext_counts.get(e, 0) for e in sig["extensions"])
            if ext_hits > 0:
                evidence.append(DetectionEvidence(
                    description=f"{ext_hits} {lang} source file(s)",
                    weight=min(ext_hits / 10, 0.6),
                ))
                score += min(ext_hits / 10, 0.6)

            # Marker file evidence
            for marker in sig["marker_files"]:
                matches = list(ws.rglob(marker))
                if matches:
                    evidence.append(DetectionEvidence(
                        file=str(matches[0].relative_to(ws)),
                        description=f"Marker file: {marker}",
                        weight=0.3,
                    ))
                    score += 0.3
                    break

            if score > 0.1:
                version = self._detect_version(lang, ws)
                detected.append(DetectedLanguage(
                    name=lang,
                    version=version,
                    confidence=min(score, 1.0),
                    evidence=evidence,
                ))

        # Enrich version for any language where the base detection had none.
        for lang in detected:
            if not lang.version:
                lang.version = self._detect_version(lang.name, ws)

        # Ensure C# appears when .cs / .csproj / .sln files exist.
        has_cs = any(f.suffix.lower() == ".cs" for f in files)
        has_proj = any(
            f.suffix.lower() in (".csproj", ".sln")
            for f in ws.rglob("*")
            if not self._is_ignored(f)
        )
        if not any(l.name == "C#" for l in detected) and (has_cs or has_proj):
            detected.append(DetectedLanguage(
                name="C#",
                version=self._detect_version("C#", ws),
                confidence=0.9,
                evidence=[DetectionEvidence(description="Found C# source/project files", weight=0.9)],
            ))

        # Sort by confidence
        return sorted(detected, key=lambda l: l.confidence, reverse=True)

    def _detect_version(self, language: str, ws: Path) -> Optional[str]:
        try:
            if language == "C#":
                versions = set()
                for csproj in ws.rglob("*.csproj"):
                    if self._is_ignored(csproj):
                        continue
                    try:
                        content = csproj.read_text(encoding="utf-8", errors="replace")
                        for v in re.findall(r"<TargetFrameworkVersion>\s*v?([\d\.]+)\s*</TargetFrameworkVersion>", content, re.IGNORECASE):
                            versions.add(f".NET Framework {v}")
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
                    def _cs_sort(v: str):
                        return (0, v) if "Framework" in v else (1, v) if "Core" in v else (2, v)
                    return ", ".join(sorted(versions, key=_cs_sort))

            elif language == "Java":
                for pom in list(ws.rglob("pom.xml"))[:5]:
                    if self._is_ignored(pom):
                        continue
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
                for grad in list(ws.rglob("build.gradle")) + list(ws.rglob("build.gradle.kts")):
                    if self._is_ignored(grad):
                        continue
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
                for fname in ["runtime.txt", ".python-version"]:
                    for p in [ws / fname] + list(ws.rglob(fname))[:3]:
                        if p.exists() and not self._is_ignored(p):
                            try:
                                raw = p.read_text(encoding="utf-8", errors="replace").strip()
                                m = re.search(r"python[-_ ]?([\d\.]+)", raw, re.IGNORECASE)
                                if m:
                                    return f"Python {m.group(1)}"
                                m = re.match(r"([\d\.]+)", raw)
                                if m:
                                    return f"Python {m.group(1)}"
                            except Exception:
                                pass
                for pp in list(ws.rglob("pyproject.toml"))[:3]:
                    if self._is_ignored(pp):
                        continue
                    try:
                        c = pp.read_text(encoding="utf-8", errors="replace")
                        m = re.search(r'python_requires\s*=\s*["\']>=?([\d\.]+)', c)
                        if m:
                            return f"Python {m.group(1)}"
                        m = re.search(r'target-version\s*=\s*["\']py(\d)(\d+)', c)
                        if m:
                            return f"Python {m.group(1)}.{m.group(2)}"
                        m = re.search(r'requires-python\s*=\s*["\']>=?([\d\.]+)', c)
                        if m:
                            return f"Python {m.group(1)}"
                    except Exception:
                        pass
                for sc in list(ws.rglob("setup.cfg"))[:3]:
                    if self._is_ignored(sc):
                        continue
                    try:
                        c = sc.read_text(encoding="utf-8", errors="replace")
                        m = re.search(r'python_requires\s*[=,]\s*>=?([\d\.]+)', c)
                        if m:
                            return f"Python {m.group(1)}"
                    except Exception:
                        pass

            elif language in ("JavaScript", "TypeScript"):
                for fname in [".nvmrc", ".node-version"]:
                    p = ws / fname
                    if p.exists():
                        try:
                            raw = p.read_text(encoding="utf-8", errors="replace").strip().lstrip("v")
                            if re.match(r"[\d\.]+", raw):
                                return f"Node {raw}"
                        except Exception:
                            pass
                for pkg in [ws / "package.json"] + list(ws.rglob("package.json"))[:3]:
                    if pkg.exists() and not self._is_ignored(pkg):
                        try:
                            data = json.loads(pkg.read_text(encoding="utf-8"))
                            node_ver = data.get("engines", {}).get("node")
                            if node_ver:
                                clean = re.sub(r"[^\d\.]", "", node_ver.split("||")[0].strip()).strip(".")
                                return f"Node {clean}" if clean else node_ver
                        except Exception:
                            pass
                if language == "TypeScript":
                    for tsc in list(ws.rglob("tsconfig.json"))[:3]:
                        if self._is_ignored(tsc):
                            continue
                        try:
                            data = json.loads(tsc.read_text(encoding="utf-8"))
                            target = data.get("compilerOptions", {}).get("target", "")
                            if target:
                                return f"TypeScript / ES{target.replace('ES', '')}"
                        except Exception:
                            pass

            elif language == "Go":
                for gomod in list(ws.rglob("go.mod"))[:3]:
                    if self._is_ignored(gomod):
                        continue
                    try:
                        c = gomod.read_text(encoding="utf-8", errors="replace")
                        m = re.search(r"^go\s+([\d\.]+)", c, re.MULTILINE)
                        if m:
                            return f"Go {m.group(1)}"
                    except Exception:
                        pass

            elif language == "PHP":
                for comp in list(ws.rglob("composer.json"))[:3]:
                    if self._is_ignored(comp):
                        continue
                    try:
                        data = json.loads(comp.read_text(encoding="utf-8"))
                        php_ver = data.get("require", {}).get("php", "")
                        if php_ver:
                            m = re.search(r"([\d\.]+)", php_ver)
                            if m:
                                return f"PHP {m.group(1)}"
                    except Exception:
                        pass

            elif language == "Ruby":
                rv = ws / ".ruby-version"
                if rv.exists():
                    try:
                        raw = rv.read_text(encoding="utf-8", errors="replace").strip()
                        m = re.search(r"([\d\.]+)", raw)
                        if m:
                            return f"Ruby {m.group(1)}"
                    except Exception:
                        pass
                gemfile = ws / "Gemfile"
                if gemfile.exists():
                    try:
                        c = gemfile.read_text(encoding="utf-8", errors="replace")
                        m = re.search(r"ruby\s+['\"]([\d\.]+)['\"]", c)
                        if m:
                            return f"Ruby {m.group(1)}"
                    except Exception:
                        pass

            elif language == "Kotlin":
                for grad in list(ws.rglob("build.gradle.kts")) + list(ws.rglob("build.gradle")):
                    if self._is_ignored(grad):
                        continue
                    try:
                        c = grad.read_text(encoding="utf-8", errors="replace")
                        m = re.search(r"jvmTarget\s*=\s*['\"]([\d\.]+)['\"]", c)
                        if m:
                            return f"Kotlin / JVM {m.group(1)}"
                        m = re.search(r'kotlin\(["\']jvm["\']\)\s+version\s+["\']([\d\.]+)', c)
                        if m:
                            return f"Kotlin {m.group(1)}"
                    except Exception:
                        pass
        except Exception:
            pass
        return None

    def _detect_frameworks(self, ws: Path, files: List[Path]) -> List[DetectedFramework]:
        detected = []
        file_contents: Dict[str, str] = {}

        def read_file(p: Path) -> str:
            if str(p) not in file_contents:
                try:
                    file_contents[str(p)] = p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    file_contents[str(p)] = ""
            return file_contents[str(p)]

        for sig in _FRAMEWORK_SIGNATURES:
            evidence = []
            found = False
            for fname in sig["files"]:
                matches = list(ws.rglob(fname))
                if matches:
                    content = read_file(matches[0])
                    for marker in sig["markers"]:
                        if marker.lower() in content.lower():
                            evidence.append(DetectionEvidence(
                                file=str(matches[0].relative_to(ws)),
                                description=f"Found '{marker}' in {fname}",
                                weight=0.8,
                            ))
                            found = True
                            break
                if found:
                    break

            if found:
                detected.append(DetectedFramework(
                    name=sig["name"],
                    language=sig["language"],
                    confidence=0.85,
                    evidence=evidence,
                ))
        return detected

    def _detect_build_systems(self, ws: Path, files: List[Path]) -> List[DetectedBuildSystem]:
        detected = []
        for sig in _BUILD_SIGNATURES:
            for fname in sig["files"]:
                if list(ws.rglob(fname)):
                    detected.append(DetectedBuildSystem(
                        name=sig["name"],
                        language=sig["language"],
                        confidence=0.9,
                        evidence=[DetectionEvidence(description=f"Found {fname}", weight=0.9)],
                    ))
                    break
        return detected

    def _detect_dependencies(self, ws: Path) -> List[DetectedDependency]:
        deps: List[DetectedDependency] = []
        seen = set()

        def add_dep(name: str, version: Optional[str], lang: str) -> None:
            if not name:
                return
            name = name.strip()
            version = version.strip() if version else None
            key = (name.lower(), lang.lower())
            if key not in seen:
                seen.add(key)
                deps.append(DetectedDependency(name=name, version=version, language=lang))

        # 1. C# packages.config
        for pkg_file in ws.rglob("packages.config"):
            if self._is_ignored(pkg_file):
                continue
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
            if self._is_ignored(csproj):
                continue
            try:
                content = csproj.read_text(encoding="utf-8", errors="replace")
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
            if self._is_ignored(pkg_file):
                continue
            try:
                data = json.loads(pkg_file.read_text(encoding="utf-8", errors="replace"))
                for dep_type in ["dependencies", "devDependencies"]:
                    for name, ver in data.get(dep_type, {}).items():
                        clean_ver = re.sub(r'^[~^>=<*\s]+', '', str(ver)).strip()
                        add_dep(name, clean_ver or None, "JavaScript")
            except Exception:
                pass

        # 4. Ruby Gemfile & Gemfile.lock
        for gfl in ws.rglob("Gemfile.lock"):
            if self._is_ignored(gfl):
                continue
            try:
                content = gfl.read_text(encoding="utf-8", errors="replace")
                for m in re.finditer(r'^\s{4}([a-zA-Z0-9_\-]+)\s+\(([\d\.]+)\)', content, re.MULTILINE):
                    add_dep(m.group(1), m.group(2), "Ruby")
            except Exception:
                pass
        for gf in ws.rglob("Gemfile"):
            if self._is_ignored(gf):
                continue
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
            if self._is_ignored(ppt):
                continue
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
            if self._is_ignored(gm):
                continue
            try:
                content = gm.read_text(encoding="utf-8", errors="replace")
                for m in re.finditer(r'^\s*([a-zA-Z0-9\.\-_/]+)\s+(v[\d\.]+)', content, re.MULTILINE):
                    add_dep(m.group(1), m.group(2).lstrip("v"), "Go")
            except Exception:
                pass

        # 7. PHP composer.json
        for comp in ws.rglob("composer.json"):
            if self._is_ignored(comp):
                continue
            try:
                data = json.loads(comp.read_text(encoding="utf-8", errors="replace"))
                for dep_type in ["require", "require-dev"]:
                    for name, ver in data.get(dep_type, {}).items():
                        if name.lower() != "php":
                            clean_ver = re.sub(r'^[~^>=<*\s]+', '', str(ver)).strip()
                            add_dep(name, clean_ver or None, "PHP")
            except Exception:
                pass

        # 8. Gradle build files (Java / Kotlin)
        for grad in list(ws.rglob("build.gradle")) + list(ws.rglob("build.gradle.kts")):
            if self._is_ignored(grad):
                continue
            try:
                content = grad.read_text(encoding="utf-8", errors="replace")
                for m in re.finditer(r'(?:implementation|api|compile|testImplementation)\s*\(?["\']([^"\':]+):([^"\':]+):([^"\':]+)["\']\)?', content):
                    add_dep(f"{m.group(1)}:{m.group(2)}", m.group(3), "Java")
            except Exception:
                pass

        # 9. Maven pom.xml
        for pom in ws.rglob("pom.xml"):
            try:
                content = pom.read_text(encoding="utf-8", errors="replace")
                for m in re.finditer(
                    r"<dependency>\s*<groupId>(.*?)</groupId>\s*<artifactId>(.*?)</artifactId>(?:\s*<version>(.*?)</version>)?",
                    content, re.DOTALL
                ):
                    add_dep(
                        f"{m.group(1).strip()}:{m.group(2).strip()}",
                        m.group(3).strip() if m.group(3) else None,
                        "Java",
                    )
            except Exception:
                pass

        # 10. requirements.txt
        for req in ws.rglob("requirements.txt"):
            try:
                for line in req.read_text(encoding="utf-8", errors="replace").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = re.split(r"[>=<!~^]", line, 1)
                        name = parts[0].strip()
                        version = line[len(name):].strip() if len(parts) > 1 else None
                        add_dep(name, version or None, "Python")
            except Exception:
                pass

        return deps[:150]

    def _detect_testing_frameworks(self, ws: Path, files: List[Path]) -> List[str]:
        found: List[str] = []
        found_set = set()

        # Pass 0: quick heuristic over any source files (base behavior).
        checks = {
            "JUnit": ["junit", "org.junit"],
            "TestNG": ["testng"],
            "pytest": ["pytest", "import pytest"],
            "unittest": ["import unittest"],
            "Jest": ["jest"],
            "Mocha": ["mocha"],
            "Go test": ["_test.go"],
            "RSpec": ["rspec"],
        }
        all_text = ""
        for f in files[:200]:
            try:
                all_text += f.read_text(encoding="utf-8", errors="replace")[:500]
            except Exception:
                pass
        for name, markers in checks.items():
            if any(m.lower() in all_text.lower() for m in markers):
                found.append(name)
                found_set.add(name)

        # Pass 1: scan manifest / project files for test package references.
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

        # Pass 2: scan TEST-SPECIFIC source files for annotations/imports.
        # Only files that are plausibly test files (by name or directory) to
        # avoid false positives from app code containing describe/expect/it.
        _TEST_DIR_PARTS = frozenset({
            "test", "tests", "spec", "specs", "__tests__", "__test__",
            "unittest", "unittests", "integration", "e2e", "acceptance",
        })
        _TEST_FILE_PATTERNS = frozenset({
            "test_", "_test.", ".test.", ".spec.", "_spec.",
            "test.", "spec.", "tests.",
        })

        def _is_test_file(p: Path) -> bool:
            for part in p.parts:
                if part.lower() in _TEST_DIR_PARTS:
                    return True
            name_lower = p.name.lower()
            if any(pat in name_lower for pat in _TEST_FILE_PATTERNS):
                return True
            stem_lower = p.stem.lower()
            if "test" in stem_lower or "spec" in stem_lower:
                return True
            return False

        source_chunks: List[str] = []
        total_chars = 0
        max_total = 4_000_000  # 4 MB total cap
        per_file_cap = 8_000  # 8 KB per file

        for f in files:
            if total_chars >= max_total:
                break
            if f.suffix.lower() not in _ALL_SOURCE_EXTENSIONS:
                continue
            if not _is_test_file(f):
                continue
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

    def _detect_databases(self, ws: Path, files: List[Path]) -> List[str]:
        found = []
        db_markers = {
            "PostgreSQL": ["postgresql", "psycopg2", "pg_"],
            "MySQL": ["mysql", "pymysql", "jdbc:mysql"],
            "SQLite": ["sqlite", "sqlite3"],
            "MongoDB": ["mongodb", "pymongo", "mongoose"],
            "Redis": ["redis", "jedis"],
            "Oracle": ["oracle", "ojdbc"],
            "SQL Server": ["sqlserver", "mssql"],
        }
        all_text = ""
        for f in files[:200]:
            try:
                all_text += f.read_text(encoding="utf-8", errors="replace")[:300]
            except Exception:
                pass
        for db, markers in db_markers.items():
            if any(m.lower() in all_text.lower() for m in markers):
                found.append(db)
        return found

    def _detect_frontend(self, ws: Path, files: List[Path]) -> List[str]:
        found = []
        markers = {
            "React": ["react"],
            "Vue.js": ["vue"],
            "Angular": ["@angular"],
            "Svelte": ["svelte"],
            "Bootstrap": ["bootstrap"],
            "Tailwind CSS": ["tailwindcss"],
        }
        pkg = ws / "package.json"
        if pkg.exists():
            try:
                import json
                data = json.loads(pkg.read_text(encoding="utf-8"))
                all_deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                for name, pkgs in markers.items():
                    if any(p in all_deps for p in pkgs):
                        found.append(name)
            except Exception:
                pass
        return found


    def _scan_documentation(self, ws: Path, files: List[Path]) -> Optional[DetectedDocumentation]:
        """
        Scan workspace for README and documentation files across root and monorepo subprojects.
        Extracts structured signals: build commands, run commands, test commands,
        target servers, databases, and environment variables.
        """
        doc_names = {"readme.md", "readme.txt", "readme.rst", "readme", "readme.markdown",
                     "install.md", "architecture.md", "contributing.md"}
        
        # Find all doc files within workspace
        found_docs: List[Path] = []
        for f in files:
            if f.name.lower() in doc_names:
                found_docs.append(f)
                
        # Also check root specifically in case it wasn't captured
        for cand in doc_names:
            p = ws / cand
            if p.exists() and p.is_file() and p not in found_docs and not self._is_ignored(p):
                found_docs.append(p)

        if not found_docs:
            return None

        # Sort: root docs first, then by path length
        def _doc_sort_key(p: Path) -> tuple:
            try:
                rel = p.relative_to(ws)
                is_root = len(rel.parts) == 1
                return (0 if is_root else 1, len(rel.parts), str(rel).lower())
            except Exception:
                return (2, 99, str(p).lower())

        found_docs.sort(key=_doc_sort_key)

        doc_items: List[DocItem] = []
        all_build = set()
        all_run = set()
        all_test = set()
        all_servers = set()
        all_databases = set()
        all_env_vars = set()

        server_keywords = {
            "iis": "IIS",
            "kestrel": "Kestrel",
            "tomcat": "Apache Tomcat",
            "apache tomcat": "Apache Tomcat",
            "nginx": "Nginx",
            "apache": "Apache HTTP Server",
            "gunicorn": "Gunicorn",
            "uvicorn": "Uvicorn",
            "docker": "Docker",
            "docker-compose": "Docker Compose",
            "kubernetes": "Kubernetes",
            "k8s": "Kubernetes",
            "azure app service": "Azure App Service",
            "azure": "Azure",
            "aws": "AWS",
            "elastic beanstalk": "AWS Elastic Beanstalk",
            "websphere": "IBM WebSphere",
            "weblogic": "Oracle WebLogic",
            "wildfly": "WildFly / JBoss",
            "jboss": "JBoss",
        }

        db_keywords = {
            "sql server": "SQL Server",
            "mssql": "SQL Server",
            "postgresql": "PostgreSQL",
            "postgres": "PostgreSQL",
            "mysql": "MySQL",
            "sqlite": "SQLite",
            "oracle": "Oracle",
            "mongodb": "MongoDB",
            "redis": "Redis",
            "rabbitmq": "RabbitMQ",
            "kafka": "Kafka",
        }

        # Regex patterns for command extraction in code blocks and bash/cmd snippets
        cmd_patterns = [
            r"```(?:bash|sh|cmd|powershell|ps1|shell|console)?\s*\n([\s\S]*?)\n```",
            r"(?:^|\n)\s*(?:[$>]|PS>)\s*([^\n]+)",
        ]

        # Scan up to 10 doc files (root + top monorepo packages)
        for doc_file in found_docs[:10]:
            try:
                rel_path = str(doc_file.relative_to(ws)).replace("\\", "/")
            except Exception:
                rel_path = doc_file.name

            is_root = "/" not in rel_path and "\\" not in rel_path

            try:
                content = doc_file.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            # Preview cap (50KB)
            preview = content[:50000]

            # 1. Extract commands from code blocks
            build_cmds = []
            run_cmds = []
            test_cmds = []

            extracted_lines = []
            for pat in cmd_patterns:
                for match in re.findall(pat, content, re.MULTILINE):
                    for line in match.splitlines():
                        line_clean = line.strip()
                        if line_clean and not line_clean.startswith("#") and not line_clean.startswith("//"):
                            line_clean = re.sub(r"^[$>]+\s*", "", line_clean).strip()
                            if line_clean:
                                extracted_lines.append(line_clean)

            # Categorize extracted command lines
            for cmd in extracted_lines:
                cmd_lower = cmd.lower()
                if any(k in cmd_lower for k in ["build", "compile", "make", "msbuild", "mvn clean", "mvn package", "gradle assemble", "dotnet publish", "cargo build", "npm run build", "yarn build"]):
                    build_cmds.append(cmd)
                    all_build.add(cmd)
                elif any(k in cmd_lower for k in ["test", "pytest", "npm test", "yarn test", "mvn test", "dotnet test", "cargo test", "ctest"]):
                    test_cmds.append(cmd)
                    all_test.add(cmd)
                elif any(k in cmd_lower for k in ["run", "start", "serve", "dotnet run", "npm start", "yarn start", "python main", "python app", "uvicorn", "gunicorn", "docker run", "docker-compose up", "flask run"]):
                    run_cmds.append(cmd)
                    all_run.add(cmd)

            # 2. Extract server mentions
            doc_servers = []
            content_lower = content.lower()
            for kw, norm_name in server_keywords.items():
                # Word boundary match to prevent substrings
                if re.search(r"\b" + re.escape(kw) + r"\b", content_lower):
                    if norm_name not in doc_servers:
                        doc_servers.append(norm_name)
                    all_servers.add(norm_name)

            # 3. Extract database mentions
            doc_dbs = []
            for kw, norm_name in db_keywords.items():
                if re.search(r"\b" + re.escape(kw) + r"\b", content_lower):
                    if norm_name not in doc_dbs:
                        doc_dbs.append(norm_name)
                    all_databases.add(norm_name)

            # 4. Extract environment variables (e.g. PORT=8080, DATABASE_URL, etc.)
            env_vars = []
            for m in re.findall(r"\b([A-Z][A-Z0-9_]{3,})\s*(?:=|[A-Za-z0-9_:/.-]+)", content):
                if m not in {"HTTP", "HTTPS", "TRUE", "FALSE", "NULL", "NONE", "JSON", "POST", "GET", "PUT", "DELETE", "README"}:
                    if m not in env_vars:
                        env_vars.append(m)
                    all_env_vars.add(m)

            item = DocItem(
                path=rel_path,
                file_name=doc_file.name,
                is_root=is_root,
                content_preview=preview,
                build_commands=build_cmds[:10],
                run_commands=run_cmds[:10],
                test_commands=test_cmds[:10],
                detected_servers=doc_servers,
                detected_databases=doc_dbs,
                environment_variables=env_vars[:20],
            )
            doc_items.append(item)

        if not doc_items:
            return None

        primary = doc_items[0]
        subprojects = doc_items[1:] if len(doc_items) > 1 else []

        return DetectedDocumentation(
            primary_readme=primary,
            subproject_readmes=subprojects,
            all_build_commands=sorted(list(all_build)),
            all_run_commands=sorted(list(all_run)),
            all_test_commands=sorted(list(all_test)),
            all_servers=sorted(list(all_servers)),
            all_databases=sorted(list(all_databases)),
            all_env_vars=sorted(list(all_env_vars)),
            total_docs_found=len(found_docs),
        )
