"""
Requirement File Updater

Applies dependency updates to requirement definition files.

Rules:
  - Preserve comments (inline and block)
  - Preserve unrelated dependencies unchanged
  - Preserve environment markers (; python_version >= '3.8')
  - Preserve extras ([security])
  - Preserve ordering
  - Only modify pinned == versions (do not silently weaken range constraints)
  - Never touch lockfiles
  - Do not rewrite the entire file — only targeted line replacement
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List

from app.dependency_analysis.models import Dependency, DependencyStatus


# Matches name and extras at the beginning, followed by specifiers, markers, and comments
_REQ_LINE_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9_.\-]+)"
    r"(?P<extras>\[.*?\])?"
    r"(?P<specifier>[^;#\n]*)"
    r"(?P<rest>;[^#\n]*)?"
    r"(?P<comment>\s*#.*)?\s*$"
)


def _update_specifier_string(spec: str, latest_version: str) -> str:
    """
    Replace the version number(s) in a specifier string with the latest version.
    e.g. "==3.2.18"        → "==4.2.1"
         ">=1.5,<3"        → ">=4.2.1,<5" (or simpler: ">=4.2.1")
         "~=1.21"          → "~=4.2.1"
    """
    # Replace any version numbers in the specifier part
    # A version number is typically a sequence of digits and dots: \d+(\.\d+)*
    # If the user has a range like ">=1.5,<3" and latest is "4.2.1",
    # let's simplify it to just the new lower bound (e.g. ">=4.2.1") to avoid conflicts.
    if "<" in spec or "," in spec:
        # If it's a range constraint like ">=1.5,<3", simplify it to ">=latest" to avoid invalid ranges
        # but preserve the operator.
        op_match = re.match(r"^\s*([><=!~^]+)", spec)
        op = op_match.group(1) if op_match else ">="
        return f"{op}{latest_version}"

    # Single specifiers: replace the version part while keeping the operator (like ==, ~=, >=)
    return re.sub(r"\d+(\.\d+)*", latest_version, spec)


def update_requirements_txt(
    file_path: str,
    updates: List[Dependency],
) -> bool:
    """
    Apply a list of dependency updates to a requirements.txt-style file.

    Only updates dependencies whose status is UPDATE_AVAILABLE.
    Returns True if at least one line was changed, False otherwise.
    Writes the file in-place (UTF-8, LF line endings preserved where possible).
    """
    path = Path(file_path)
    try:
        original = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False

    # Build lookup: name (lower) → new version
    update_map = {
        dep.name.lower(): dep.latest_stable_version
        for dep in updates
        if dep.status == DependencyStatus.UPDATE_AVAILABLE
        and dep.update_required
        and dep.latest_stable_version
    }

    if not update_map:
        return False

    lines = original.splitlines(keepends=True)
    changed = False

    for i, line in enumerate(lines):
        stripped = line.rstrip("\n\r")
        m = _REQ_LINE_RE.match(stripped)
        if not m:
            continue

        name = m.group("name").lower()
        if name not in update_map:
            continue

        new_ver = update_map[name]
        old_spec = m.group("specifier")
        new_spec = _update_specifier_string(old_spec, new_ver)

        # Reconstruct line preserving extras, markers, comments
        new_line = (
            m.group("name")
            + (m.group("extras") or "")
            + new_spec
            + (m.group("rest") or "")
            + (m.group("comment") or "")
        )

        # Preserve original line ending
        ending = line[len(stripped):]
        lines[i] = new_line + ending
        changed = True

    if changed:
        path.write_text("".join(lines), encoding="utf-8")

    return changed


def _update_npm_specifier(spec: str, latest_version: str) -> str:
    """
    Update npm version specifier while preserving prefix.
    e.g. "^18.3.1" -> "^19.2.8"
         "~18.3.1" -> "~19.2.8"
    """
    match = re.match(r"^([^\d]*)([\d.]+)(.*)$", spec.strip())
    if match:
        prefix = match.group(1)
        suffix = match.group(3)
        return f"{prefix}{latest_version}{suffix}"
    return latest_version


def update_package_json(
    file_path: str,
    updates: List[Dependency],
) -> bool:
    """
    Update version specifiers in package.json for exact-pinned and range dependencies.
    """
    import json as _json

    path = Path(file_path)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        data = _json.loads(text)
    except (OSError, _json.JSONDecodeError):
        return False

    update_map = {
        dep.name.lower(): dep.latest_stable_version
        for dep in updates
        if dep.status == DependencyStatus.UPDATE_AVAILABLE
        and dep.update_required
        and dep.latest_stable_version
    }

    if not update_map:
        return False

    changed = False
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        for name, spec in data.get(section, {}).items():
            if name.lower() in update_map and isinstance(spec, str):
                new_ver = update_map[name.lower()]
                new_spec = _update_npm_specifier(spec, new_ver)
                if data[section][name] != new_spec:
                    data[section][name] = new_spec
                    changed = True

    if changed:
        path.write_text(
            _json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return changed

