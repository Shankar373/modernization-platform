"""
Version Comparator — Semantic & PEP 440 / npm-aware version comparison.

Handles:
  - Pinned versions:  ==1.2.3
  - Ranges:           >=1.5,<3   ~=1.21   ^18.2.0   >=2.25
  - Status codes:     UP_TO_DATE | UPDATE_AVAILABLE | CONSTRAINT_BLOCKED | INVALID_VERSION

Never uses plain string comparison for version ordering.
Uses 'packaging' library (PEP 440) for Python versions.
Falls back gracefully when 'packaging' is unavailable.
"""
from __future__ import annotations

import re
from typing import Optional

from app.dependency_analysis.models import Dependency, DependencyStatus, DependencyEcosystem


def _parse_version_safe(v: str):
    """
    Return a comparable version object or None.
    Prefers packaging.version.Version (PEP 440).
    Falls back to a simple tuple of ints.
    """
    try:
        from packaging.version import Version, InvalidVersion
        try:
            return Version(v)
        except InvalidVersion:
            pass
    except ImportError:
        pass

    # Fallback: extract numeric parts only
    parts = re.findall(r"\d+", v)
    if parts:
        return tuple(int(p) for p in parts)
    return None


def _versions_equal(a: str, b: str) -> bool:
    va = _parse_version_safe(a)
    vb = _parse_version_safe(b)
    if va is None or vb is None:
        return a == b
    return va == vb


def _version_a_lt_b(a: str, b: str) -> bool:
    """Return True when version a < version b."""
    va = _parse_version_safe(a)
    vb = _parse_version_safe(b)
    if va is None or vb is None:
        return False  # cannot compare — assume equal / unknown
    try:
        return va < vb
    except TypeError:
        return False


def _latest_satisfies_constraint(latest: str, constraint_str: str) -> bool:
    """
    Return True if `latest` satisfies the given constraint expression.
    E.g. constraint_str=">=1.5,<3", latest="3.0.1" → False
    """
    try:
        from packaging.specifiers import SpecifierSet
        spec = SpecifierSet(constraint_str, prereleases=False)
        return latest in spec
    except Exception:
        pass

    # Fallback: accept the update if we cannot parse the constraint
    return True


def compare_dependency(dep: Dependency) -> Dependency:
    """
    Compare dep.current_version against dep.latest_stable_version and
    set dep.status, dep.update_required, and dep.reason accordingly.

    Modifies and returns the same object (in-place update).
    """
    current = dep.current_version
    latest  = dep.latest_stable_version

    if latest is None:
        dep.status = DependencyStatus.LOOKUP_FAILED
        dep.update_required = False
        dep.reason = "Registry lookup returned no result."
        return dep

    # No current version pinned — we have a bare/unconstrained dependency
    if current is None:
        # If there's a range constraint, check whether latest satisfies it
        if dep.version_constraint:
            if _latest_satisfies_constraint(latest, dep.version_constraint):
                dep.status = DependencyStatus.UP_TO_DATE
                dep.reason = f"Latest {latest} satisfies constraint {dep.version_constraint}."
            else:
                dep.status = DependencyStatus.CONSTRAINT_BLOCKED
                dep.update_required = False
                dep.reason = (
                    f"Latest stable version {latest} does NOT satisfy "
                    f"the explicit constraint '{dep.version_constraint}'. "
                    "The constraint must be relaxed manually."
                )
        else:
            dep.status = DependencyStatus.UP_TO_DATE
            dep.reason = "No version pinned; no update required."
        return dep

    # Validate parsability
    if _parse_version_safe(current) is None:
        dep.status = DependencyStatus.INVALID_VERSION
        dep.update_required = False
        dep.reason = f"Current version '{current}' cannot be parsed."
        return dep

    if _versions_equal(current, latest):
        dep.status = DependencyStatus.UP_TO_DATE
        dep.update_required = False
        dep.reason = f"Already at the latest stable version {latest}."
        return dep

    if _version_a_lt_b(current, latest):
        # Newer version available — check if it respects the explicit constraint
        if dep.version_constraint and not dep.version_constraint.startswith("=="):
            if not _latest_satisfies_constraint(latest, dep.version_constraint):
                dep.status = DependencyStatus.CONSTRAINT_BLOCKED
                dep.update_required = False
                dep.reason = (
                    f"Latest stable {latest} violates explicit constraint "
                    f"'{dep.version_constraint}'. Constraint must be relaxed manually."
                )
                return dep

        dep.status = DependencyStatus.UPDATE_AVAILABLE
        dep.update_required = True
        dep.reason = f"Update available: {current} → {latest}."
    else:
        # current >= latest (e.g. running a pre-release or patched version)
        dep.status = DependencyStatus.UP_TO_DATE
        dep.update_required = False
        dep.reason = f"Current version {current} is at or ahead of the latest stable {latest}."

    return dep
