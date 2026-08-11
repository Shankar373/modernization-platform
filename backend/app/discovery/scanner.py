"""
Universal Codebase Scanner — technology discovery engine.

Detects programming languages, versions, frameworks, build systems,
dependencies, databases, testing frameworks, and frontend technologies.

All detections include confidence scores and evidence lists.
Detection is never claimed to be perfect.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.core.domain.models import (
    DetectedBuildSystem,
    DetectedDependency,
    DetectedFramework,
    DetectedLanguage,
    DetectionEvidence,
    TechnologyProfile,
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
        "marker_files": [".csproj", ".sln"],
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
        profile.is_multi_language = len(profile.languages) > 1

        return profile

    def _is_ignored(self, f: Path) -> bool:
        parts = f.parts
        ignore_dirs = {".git", "node_modules", ".venv", "venv", "__pycache__", ".idea", "target", "build", "dist"}
        return any(p in ignore_dirs for p in parts)

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

        # Sort by confidence
        return sorted(detected, key=lambda l: l.confidence, reverse=True)

    def _detect_version(self, language: str, ws: Path) -> Optional[str]:
        try:
            if language == "Java":
                pom = ws / "pom.xml"
                if pom.exists():
                    content = pom.read_text(encoding="utf-8", errors="replace")
                    m = re.search(r"<java\.version>(\d+(?:\.\d+)?)</java\.version>", content)
                    if m:
                        return m.group(1)
                    m = re.search(r"<source>(\d+(?:\.\d+)?)</source>", content)
                    if m:
                        return m.group(1)
            elif language == "Python":
                for fname in ["pyproject.toml", ".python-version"]:
                    f = ws / fname
                    if f.exists():
                        content = f.read_text(encoding="utf-8", errors="replace")
                        m = re.search(r'python_requires\s*=\s*["\']>=?(\d+\.\d+)', content)
                        if m:
                            return m.group(1)
                        m = re.search(r'target-version\s*=\s*["\']py(\d)(\d+)', content)
                        if m:
                            return f"{m.group(1)}.{m.group(2)}"
            elif language in ("JavaScript", "TypeScript"):
                pkg = ws / "package.json"
                if pkg.exists():
                    import json
                    data = json.loads(pkg.read_text(encoding="utf-8"))
                    return data.get("engines", {}).get("node")
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
        deps = []
        # Maven pom.xml
        for pom in ws.rglob("pom.xml"):
            try:
                content = pom.read_text(encoding="utf-8", errors="replace")
                for m in re.finditer(
                    r"<dependency>\s*<groupId>(.*?)</groupId>\s*<artifactId>(.*?)</artifactId>(?:\s*<version>(.*?)</version>)?",
                    content, re.DOTALL
                ):
                    deps.append(DetectedDependency(
                        name=f"{m.group(1).strip()}:{m.group(2).strip()}",
                        version=m.group(3).strip() if m.group(3) else None,
                        language="Java",
                    ))
            except Exception:
                pass

        # requirements.txt
        for req in ws.rglob("requirements.txt"):
            try:
                for line in req.read_text(encoding="utf-8", errors="replace").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = re.split(r"[>=<!~^]", line, 1)
                        name = parts[0].strip()
                        version = line[len(name):].strip() if len(parts) > 1 else None
                        deps.append(DetectedDependency(name=name, version=version, language="Python"))
            except Exception:
                pass

        return deps[:100]  # Cap at 100 to avoid huge profiles

    def _detect_testing_frameworks(self, ws: Path, files: List[Path]) -> List[str]:
        found = []
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
