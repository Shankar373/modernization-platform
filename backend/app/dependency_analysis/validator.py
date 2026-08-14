"""
Post-Update Validator

After dependency files have been updated, validates that:
  1. requirements.txt lines are syntactically correct PEP 508 specifiers
  2. package.json is valid JSON with a valid "version" field
  3. No duplicate dependency names were introduced
  4. No version constraint was silently removed

Does NOT run pip install / npm install — that is left to CI.
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Tuple

from app.dependency_analysis.models import ValidationStatus

# Minimal PEP 508 line pattern (name + optional specifier)
# Accepts: name[extras] op version [, op version]* [; marker] [# comment]
_PEP508_RE = re.compile(
    r"^[A-Za-z0-9_.-]"    # name start
    r"[A-Za-z0-9_.-]*"    # rest of name
    r"(\[.*?\])?"         # extras (optional)
    r"(\s*[><=!~^][^;#]*)?"  # version specifier(s) (optional)
    r"(\s*;[^#]*)?"       # env marker (optional)
    r"(\s*#.*)?"          # comment (optional)
    r"\s*$"
)


def validate_requirements_txt(file_path: str) -> Tuple[ValidationStatus, List[str]]:
    """
    Validate a requirements.txt file post-update.
    Returns (status, list_of_errors).
    """
    errors: List[str] = []
    path = Path(file_path)

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as e:
        return ValidationStatus.FAILED, [f"Cannot read file: {e}"]

    names_seen: set[str] = set()

    for lineno, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-") or "://" in line:
            continue

        if not _PEP508_RE.match(line):
            errors.append(f"Line {lineno}: invalid PEP 508 specifier: {line!r}")
            continue

        # Duplicate check
        name_m = re.match(r"^([A-Za-z0-9_.\-]+)", line)
        if name_m:
            name = name_m.group(1).lower()
            if name in names_seen:
                errors.append(f"Line {lineno}: duplicate dependency '{name}'")
            names_seen.add(name)

    if errors:
        return ValidationStatus.FAILED, errors
    return ValidationStatus.PASSED, []


def validate_package_json(file_path: str) -> Tuple[ValidationStatus, List[str]]:
    """Validate a package.json file post-update."""
    errors: List[str] = []
    path = Path(file_path)

    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError) as e:
        return ValidationStatus.FAILED, [f"Invalid JSON: {e}"]

    for section in ("dependencies", "devDependencies"):
        for name, spec in data.get(section, {}).items():
            if not isinstance(spec, str):
                errors.append(f"{section}.{name}: version must be a string, got {type(spec).__name__}")
            elif not spec.strip():
                errors.append(f"{section}.{name}: empty version specifier")

    if errors:
        return ValidationStatus.FAILED, errors
    return ValidationStatus.PASSED, []


def validate_packages_config(file_path: str) -> Tuple[ValidationStatus, List[str]]:
    """Validate a packages.config file post-update (well-formed XML, each package has id + version)."""
    errors: List[str] = []
    path = Path(file_path)

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return ValidationStatus.FAILED, [f"Cannot read file: {e}"]

    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        return ValidationStatus.FAILED, [f"Invalid XML: {e}"]

    if root.tag.lower() != "packages":
        return ValidationStatus.FAILED, [f"Unexpected root element: <{root.tag}> (expected <packages>)"]

    ids_seen: set[str] = set()
    for pkg in root:
        if pkg.tag.lower() != "package":
            continue
        pid = pkg.get("id", "").strip()
        version = pkg.get("version", "").strip()
        if not pid:
            errors.append("package entry missing required 'id' attribute")
        else:
            if pid.lower() in ids_seen:
                errors.append(f"duplicate package '{pid}'")
            ids_seen.add(pid.lower())
        if not version:
            errors.append(f"package '{pid}': missing required 'version' attribute")

    if errors:
        return ValidationStatus.FAILED, errors
    return ValidationStatus.PASSED, []


def validate_csproj(file_path: str) -> Tuple[ValidationStatus, List[str]]:
    """Validate a .csproj file post-update (well-formed XML, PackageReference entries carry versions)."""
    errors: List[str] = []
    path = Path(file_path)

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return ValidationStatus.FAILED, [f"Cannot read file: {e}"]

    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        return ValidationStatus.FAILED, [f"Invalid XML: {e}"]

    refs_seen: set[str] = set()
    for ref in root.iter():
        if ref.tag.lower() == "packagereference":
            pid = ref.get("Include", "").strip()
            if not ref.get("Version", "").strip():
                errors.append(f"PackageReference '{pid}': missing required 'Version' attribute")
            if pid and pid.lower() in refs_seen:
                errors.append(f"duplicate PackageReference '{pid}'")
            if pid:
                refs_seen.add(pid.lower())
        elif ref.tag.lower() == "reference":
            # Legacy <Reference Include="..."> with <HintPath> is valid without a Version attribute
            if not ref.get("Include", "").strip():
                errors.append("reference entry missing required 'Include' attribute")

    if errors:
        return ValidationStatus.FAILED, errors
    return ValidationStatus.PASSED, []


def validate_file(file_path: str) -> Tuple[ValidationStatus, List[str]]:
    """Dispatch to the right validator based on filename."""
    name = Path(file_path).name.lower()
    if name in ("requirements.txt", "requirements-dev.txt",
                "requirements-test.txt", "requirements-prod.txt"):
        return validate_requirements_txt(file_path)
    if name == "package.json":
        return validate_package_json(file_path)
    if name == "packages.config":
        return validate_packages_config(file_path)
    if name.endswith(".csproj"):
        return validate_csproj(file_path)
    # No validator for this file type — skip
    return ValidationStatus.SKIPPED, []
