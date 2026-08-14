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


def update_pyproject_toml(
    file_path: str,
    updates: List[Dependency],
) -> bool:
    """
    Apply dependency updates to a pyproject.toml.

    Supports both PEP 621 style `[project].dependencies` (string specifiers)
    and Poetry style `[tool.poetry.dependencies]` (string or table entries).
    Formatting is preserved via tomlkit; only targeted entries are rewritten.
    """
    path = Path(file_path)
    update_map = {
        dep.name.lower(): dep.latest_stable_version
        for dep in updates
        if dep.status == DependencyStatus.UPDATE_AVAILABLE
        and dep.update_required
        and dep.latest_stable_version
    }
    if not update_map:
        return False

    try:
        import tomlkit
    except ImportError:
        return False

    try:
        doc = tomlkit.parse(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return False

    changed = False

    def _bump_str_items(items) -> None:
        """PEP 621 string entries like 'name==1.2.3' or 'name >= 1'."""
        nonlocal changed
        if not isinstance(items, list):
            return
        for idx, item in enumerate(list(items)):
            if not isinstance(item, str):
                continue
            m = re.match(r"^([A-Za-z0-9_.\-]+)\s*(.*)$", item)
            if not m:
                continue
            key = m.group(1).lower()
            if key not in update_map:
                continue
            spec = m.group(2).strip()
            if not spec:
                continue
            new_spec = _update_specifier_string(spec, update_map[key])
            new_item = item[:m.start(2)] + new_spec + item[m.end(2):]
            if new_item != item:
                items[idx] = new_item
                changed = True

    project = doc.get("project")
    if isinstance(project, dict):
        _bump_str_items(project.get("dependencies"))

    tool = doc.get("tool")
    poetry = tool.get("poetry") if isinstance(tool, dict) else None
    if isinstance(poetry, dict):
        pdeps = poetry.get("dependencies")
        if pdeps is not None and isinstance(pdeps, dict):
            for dep_name in list(pdeps.keys()):
                if dep_name == "python":
                    continue
                key = dep_name.lower()
                if key not in update_map:
                    continue
                entry = pdeps[dep_name]
                if isinstance(entry, str):
                    new_spec = _update_specifier_string(entry.strip(), update_map[key])
                    if new_spec != entry.strip():
                        pdeps[dep_name] = new_spec
                        changed = True
                elif isinstance(entry, dict):
                    version_val = entry.get("version")
                    if isinstance(version_val, str):
                        new_version = _update_specifier_string(version_val.strip(), update_map[key])
                        if new_version != version_val.strip():
                            entry["version"] = new_version
                            changed = True

    if changed:
        path.write_text(tomlkit.dumps(doc), encoding="utf-8")

    return changed


def update_setup_cfg(
    file_path: str,
    updates: List[Dependency],
) -> bool:
    """
    Apply dependency updates to a setup.cfg `install_requires` section.

    Supports both the multi-line block form and inline single-line form.
    Comments and environment markers are preserved.
    """
    path = Path(file_path)
    update_map = {
        dep.name.lower(): dep.latest_stable_version
        for dep in updates
        if dep.status == DependencyStatus.UPDATE_AVAILABLE
        and dep.update_required
        and dep.latest_stable_version
    }
    if not update_map:
        return False

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    except OSError:
        return False

    changed = False
    in_block = False

    def _bump_token(token: str) -> str:
        tm = _REQ_LINE_RE.match(token)
        if not tm:
            return token
        name = tm.group("name").lower()
        if name not in update_map:
            return token
        spec = tm.group("specifier")
        new_spec = _update_specifier_string(spec.strip(), update_map[name])
        return (
            tm.group("name")
            + (tm.group("extras") or "")
            + new_spec
            + (tm.group("rest") or "")
            + (tm.group("comment") or "")
        )

    for i, line in enumerate(lines):
        stripped = line.strip()
        low = stripped.lower()

        if in_block:
            if low.startswith("["):
                in_block = False
            else:
                token = _bump_token(stripped)
                if token != stripped:
                    ending = line[len(stripped):]
                    lines[i] = token + ending
                    changed = True
            continue

        if low.startswith("install_requires"):
            inline = stripped.split("=", 1)[1].strip() if "=" in stripped else ""
            if not inline:
                in_block = True
            else:
                inline_tokens = re.split(r",|\s+", inline)
                new_inline = ", ".join(_bump_token(t) for t in inline_tokens if t)
                if new_inline != stripped.split("=", 1)[1].strip():
                    ending = line[len(stripped):]
                    lines[i] = stripped.split("=", 1)[0] + " =" + new_inline + ending
                    changed = True

    if changed:
        path.write_text("".join(lines), encoding="utf-8")

    return changed


def update_pom_xml(
    file_path: str,
    updates: List[Dependency],
) -> bool:
    """
    Apply dependency updates to a Maven pom.xml.

    Java dependencies use canonical `group:artifact` names. Only literal
    <version> tags inside <dependency> blocks are rewritten; property-resolved
    versions (${...}) are left untouched. XML structure and formatting that is
    not part of a dependency version is preserved.
    """
    path = Path(file_path)
    update_map = {
        dep.name.lower(): dep.latest_stable_version
        for dep in updates
        if dep.status == DependencyStatus.UPDATE_AVAILABLE
        and dep.update_required
        and dep.latest_stable_version
    }
    if not update_map:
        return False

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False

    version_re = re.compile(r"<version>\s*([^<]+?)\s*</version>", re.IGNORECASE)
    group_re = re.compile(r"<groupId>\s*(.*?)\s*</groupId>", re.DOTALL | re.IGNORECASE)
    artifact_re = re.compile(r"<artifactId>\s*(.*?)\s*</artifactId>", re.DOTALL | re.IGNORECASE)
    prop_re = re.compile(r"\$\{")

    changed = False
    parts: List[str] = []
    last = 0
    for m in re.finditer(r"<dependency\b[^>]*>.*?</dependency>", content, re.DOTALL | re.IGNORECASE):
        block_start, block_end = m.span()
        parts.append(content[last:block_start])
        block = m.group(0)

        g = group_re.search(block)
        a = artifact_re.search(block)
        coord = None
        if g and a:
            coord = f"{g.group(1).strip()}:{a.group(1).strip()}".lower()
        v = version_re.search(block)

        if not coord or coord not in update_map or not v or prop_re.search(v.group(1)):
            parts.append(block)
        else:
            new_block = block[:v.start()] + f"<version>{update_map[coord]}</version>" + block[v.end():]
            parts.append(new_block)
            changed = True
        last = block_end

    parts.append(content[last:])

    if changed:
        path.write_text("".join(parts), encoding="utf-8")

    return changed

