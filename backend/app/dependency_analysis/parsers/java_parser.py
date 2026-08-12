"""
Java Dependency Parser (Maven pom.xml)

Parses <dependency> blocks from pom.xml files.
Handles property placeholders (${project.version} etc.) gracefully.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from app.dependency_analysis.models import (
    Dependency,
    DependencyEcosystem,
    DependencyStatus,
)

# Matches a single <dependency> block
_DEP_BLOCK_RE = re.compile(
    r"<dependency>\s*"
    r"<groupId>\s*(.*?)\s*</groupId>\s*"
    r"<artifactId>\s*(.*?)\s*</artifactId>\s*"
    r"(?:<version>\s*(.*?)\s*</version>)?\s*"
    r"(?:<scope>\s*(.*?)\s*</scope>)?",
    re.DOTALL,
)

# Maven property placeholder like ${spring.version}
_PROPERTY_RE = re.compile(r"\$\{[^}]+\}")


def parse_pom_xml(file_path: str) -> List[Dependency]:
    """Parse <dependency> entries from a Maven pom.xml."""
    deps: List[Dependency] = []
    path = Path(file_path)

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return deps

    for m in _DEP_BLOCK_RE.finditer(content):
        group_id    = m.group(1).strip()
        artifact_id = m.group(2).strip()
        raw_version = m.group(3).strip() if m.group(3) else None
        scope       = m.group(4).strip() if m.group(4) else None

        # Build canonical Maven coordinate as the dependency name
        name = f"{group_id}:{artifact_id}"

        # Skip property-resolved versions (runtime placeholders)
        pinned: Optional[str] = None
        if raw_version and not _PROPERTY_RE.search(raw_version):
            pinned = raw_version

        deps.append(Dependency(
            name=name,
            current_version=pinned,
            version_constraint=f"=={pinned}" if pinned else None,
            source_file="pom.xml",
            ecosystem=DependencyEcosystem.JAVA,
            status=DependencyStatus.LOOKUP_FAILED,
        ))

    return deps
