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


# Matches "name[extras]==version; marker  # comment"
_REQ_LINE_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9_.\-]+)"
    r"(?P<extras>\[.*?\])?"
    r"(?P<spec>\s*==\s*[\d.]+)"
    r"(?P<rest>[^#\n]*)"
    r"(?P<comment>\s*#.*)?\s*$"
)


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
        new_spec = f"=={new_ver}"

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


def update_package_json(
    file_path: str,
    updates: List[Dependency],
) -> bool:
    """
    Update version specifiers in package.json for exact-pinned dependencies.

    Only updates exact version pins (no ^ or ~ prefix in the specifier).
    Returns True if any changes were made.
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
        and dep.current_version is not None  # only update pinned entries
    }

    if not update_map:
        return False

    changed = False
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        for name, spec in data.get(section, {}).items():
            if name.lower() in update_map and isinstance(spec, str):
                # Only update exact pins (no range prefix)
                if re.match(r"^\d+(\.\d+)*$", spec.strip()):
                    data[section][name] = update_map[name.lower()]
                    changed = True

    if changed:
        path.write_text(
            _json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return changed
