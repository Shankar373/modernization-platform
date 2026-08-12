"""
Node.js / JavaScript / TypeScript Dependency Parser

Parses package.json dependencies and devDependencies.
Lockfiles (package-lock.json, yarn.lock, pnpm-lock.yaml) are detected
but intentionally NOT parsed for updates — only flagged.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Optional, Tuple

from app.dependency_analysis.models import (
    Dependency,
    DependencyEcosystem,
    DependencyStatus,
)


def _parse_npm_version(spec: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse an npm version specifier into (pinned_version, constraint_expr).
    e.g. "^18.2.0" → ("18.2.0", "^18.2.0")
         "18.2.0"  → ("18.2.0", "18.2.0")
         ">=18"    → ("18",     ">=18")
         "*"       → (None,     None)
    """
    spec = spec.strip()
    if not spec or spec in ("*", "latest", "x"):
        return None, None

    # Exact version (no prefix)
    if re.match(r"^\d+(\.\d+)*$", spec):
        return spec, spec

    # Range fallback: extract the first version number in the specifier string
    v_match = re.search(r"(\d+(\.\d+)*)", spec)
    if v_match:
        return v_match.group(1), spec

    return None, spec



def parse_package_json(file_path: str) -> List[Dependency]:
    """Parse dependencies and devDependencies from package.json."""
    deps: List[Dependency] = []
    path = Path(file_path)
    rel = path.name

    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return deps

    for section in ("dependencies", "devDependencies", "peerDependencies"):
        for name, spec in data.get(section, {}).items():
            if not isinstance(spec, str):
                continue
            pinned, constraint = _parse_npm_version(spec)
            deps.append(Dependency(
                name=name,
                current_version=pinned,
                version_constraint=constraint,
                source_file=rel,
                ecosystem=DependencyEcosystem.NODE,
                status=DependencyStatus.LOOKUP_FAILED,
            ))

    return deps
