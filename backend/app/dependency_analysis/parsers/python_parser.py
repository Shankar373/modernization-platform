"""
Python Dependency Parser

Parses requirements.txt / requirements-*.txt, pyproject.toml (PEP 621 / Poetry),
setup.cfg, setup.py, and Pipfile.

Normalises each dependency into the Dependency domain model.
Does NOT contact any network registry — pure file parsing only.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple

from app.dependency_analysis.models import (
    Dependency,
    DependencyEcosystem,
    DependencyStatus,
)


# ── Requirements-file line parser ────────────────────────────────────────────

# Supported specifier operators
_SPECIFIER_RE = re.compile(
    r"^([A-Za-z0-9_.\-]+)"       # package name
    r"(\[.*?\])?"                 # optional extras [security,tls]
    r"(\s*(?:[><=!~^,\s]+[^\s;#]+)*)?"  # version specifier(s)
    r"(\s*;[^#]*)?"               # environment marker
    r"(\s*#.*)?$"                 # comment
)

# Pin pattern: name==1.2.3
_PINNED_RE = re.compile(r"^==\s*(.+)$")


def _parse_specifier(raw: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Split a version specifier string into (pinned_version, constraint_expr).
    e.g. "==2.28.0"        → ("2.28.0", "==2.28.0")
         ">=1.5,<3"        → ("1.5",     ">=1.5,<3")
         "~=1.21"          → ("1.21",    "~=1.21")
         ""                → (None,      None)
    """
    spec = raw.strip()
    if not spec:
        return None, None
    pin = _PINNED_RE.match(spec)
    if pin:
        return pin.group(1).strip(), spec

    # Range/specifier fallback: extract the first version number in the specifier string
    v_match = re.search(r"(\d+(\.\d+)*)", spec)
    if v_match:
        return v_match.group(1), spec

    return None, spec



def parse_requirements_txt(file_path: str) -> List[Dependency]:
    """Parse a requirements.txt-style file (handles all flavours)."""
    deps: List[Dependency] = []
    path = Path(file_path)
    rel = path.name

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return deps

    for raw_line in lines:
        line = raw_line.strip()

        # Skip empty lines, comments, option flags, URL requirements
        if not line or line.startswith("#") or line.startswith("-") or "://" in line:
            continue

        m = _SPECIFIER_RE.match(line)
        if not m:
            continue

        name      = m.group(1).strip() if m.group(1) else None
        extras    = m.group(2).strip() if m.group(2) else None
        spec_raw  = m.group(3).strip() if m.group(3) else ""
        marker    = m.group(4).strip() if m.group(4) else None

        if not name:
            continue

        pinned, constraint = _parse_specifier(spec_raw)
        deps.append(Dependency(
            name=name,
            current_version=pinned,
            version_constraint=constraint,
            source_file=rel,
            ecosystem=DependencyEcosystem.PYTHON,
            status=DependencyStatus.LOOKUP_FAILED,
            extras=extras,
            environment_marker=marker,
        ))

    return deps


def parse_pyproject_toml(file_path: str) -> List[Dependency]:
    """Parse PEP 621 [project.dependencies] and Poetry [tool.poetry.dependencies]."""
    deps: List[Dependency] = []
    path = Path(file_path)

    try:
        import tomlkit
        data = tomlkit.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return deps

    source = "pyproject.toml"

    # PEP 621: [project] dependencies list
    project_deps = data.get("project", {}).get("dependencies", [])
    for raw in project_deps:
        if isinstance(raw, str):
            m = _SPECIFIER_RE.match(raw.strip())
            if m and m.group(1):
                name = m.group(1).strip()
                spec_raw = m.group(3).strip() if m.group(3) else ""
                pinned, constraint = _parse_specifier(spec_raw)
                deps.append(Dependency(
                    name=name,
                    current_version=pinned,
                    version_constraint=constraint,
                    source_file=source,
                    ecosystem=DependencyEcosystem.PYTHON,
                    status=DependencyStatus.LOOKUP_FAILED,
                ))

    # Poetry: [tool.poetry.dependencies]
    poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
    for name, spec in poetry_deps.items():
        if name.lower() in ("python",):
            continue  # skip the python version constraint
        if isinstance(spec, str):
            pinned, constraint = _parse_specifier(spec)
            deps.append(Dependency(
                name=name,
                current_version=pinned,
                version_constraint=constraint,
                source_file=source,
                ecosystem=DependencyEcosystem.PYTHON,
                status=DependencyStatus.LOOKUP_FAILED,
            ))
        elif isinstance(spec, dict):
            ver = spec.get("version", "")
            pinned, constraint = _parse_specifier(str(ver))
            deps.append(Dependency(
                name=name,
                current_version=pinned,
                version_constraint=constraint,
                source_file=source,
                ecosystem=DependencyEcosystem.PYTHON,
                status=DependencyStatus.LOOKUP_FAILED,
            ))

    return deps


def parse_setup_cfg(file_path: str) -> List[Dependency]:
    """Parse install_requires from setup.cfg."""
    deps: List[Dependency] = []
    path = Path(file_path)

    try:
        import configparser
        cfg = configparser.ConfigParser()
        cfg.read_string(path.read_text(encoding="utf-8", errors="replace"))
        raw_list = cfg.get("options", "install_requires", fallback="")
    except Exception:
        return deps

    for raw in raw_list.strip().splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        m = _SPECIFIER_RE.match(raw)
        if m and m.group(1):
            name = m.group(1).strip()
            spec_raw = m.group(3).strip() if m.group(3) else ""
            pinned, constraint = _parse_specifier(spec_raw)
            deps.append(Dependency(
                name=name,
                current_version=pinned,
                version_constraint=constraint,
                source_file="setup.cfg",
                ecosystem=DependencyEcosystem.PYTHON,
                status=DependencyStatus.LOOKUP_FAILED,
            ))

    return deps


def parse_pipfile(file_path: str) -> List[Dependency]:
    """Parse [packages] section from a Pipfile (TOML-like)."""
    deps: List[Dependency] = []
    path = Path(file_path)

    try:
        import tomlkit
        data = tomlkit.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return deps

    for section in ("packages", "dev-packages"):
        for name, spec in data.get(section, {}).items():
            if isinstance(spec, str):
                if spec.strip() == "*":
                    pinned, constraint = None, None
                else:
                    pinned, constraint = _parse_specifier(spec)
                deps.append(Dependency(
                    name=name,
                    current_version=pinned,
                    version_constraint=constraint,
                    source_file="Pipfile",
                    ecosystem=DependencyEcosystem.PYTHON,
                    status=DependencyStatus.LOOKUP_FAILED,
                ))

    return deps
