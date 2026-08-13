"""
Package Registry Client — Dynamic Latest-Stable-Version Lookup

Queries the appropriate package registry for each ecosystem:
  Python → PyPI   JSON API (https://pypi.org/pypi/<name>/json)
  Node   → npm registry (https://registry.npmjs.org/<name>)
  Java   → Maven Central Search REST API

Rules enforced:
  - NEVER hard-code package versions.
  - NEVER return a placeholder such as "latest" or "x.x.x".
  - Filter out alpha / beta / rc / dev / nightly pre-releases.
  - On network failure → return None; caller sets status=LOOKUP_FAILED.
  - Timeouts: 8 s per request (configurable).
"""
from __future__ import annotations

import logging
import re
from typing import Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import json

from app.dependency_analysis.models import DependencyEcosystem

log = logging.getLogger(__name__)

_TIMEOUT = 8  # seconds

# Pre-release markers — any version string containing these is excluded
_PRE_RELEASE_RE = re.compile(
    r"(alpha|beta|rc\d*|dev\d*|pre\d*|nightly|snapshot|a\d+|b\d+)",
    re.IGNORECASE,
)


def _is_stable(version: str) -> bool:
    """Return True if the version string looks like a stable release."""
    return not bool(_PRE_RELEASE_RE.search(version))


def _http_get_json(url: str) -> Optional[dict]:
    """Perform a plain HTTP GET and return parsed JSON or None on error."""
    try:
        req = Request(url, headers={"User-Agent": "ModernizationPlatform/1.0"})
        with urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError, OSError, json.JSONDecodeError) as exc:
        log.debug("Registry fetch failed for %s: %s", url, exc)
        return None


# ── PyPI ────────────────────────────────────────────────────────────────────

def _latest_pypi(name: str) -> Optional[str]:
    """
    Query PyPI JSON API for the latest stable release.
    https://pypi.org/pypi/<name>/json
    """
    data = _http_get_json(f"https://pypi.org/pypi/{name}/json")
    if not data:
        return None

    # PyPI returns info.version as the "latest" but it may be a pre-release.
    # We iterate releases sorted descending and pick the first stable one.
    releases = data.get("releases", {})
    stable_versions = [v for v in releases if _is_stable(v) and releases[v]]
    if not stable_versions:
        return None

    try:
        from packaging.version import Version
        stable_versions.sort(key=lambda v: Version(v), reverse=True)
        return stable_versions[0]
    except ImportError:
        # Fallback without packaging library — use lexicographic sort (less accurate)
        stable_versions.sort(reverse=True)
        return stable_versions[0]


# ── npm ─────────────────────────────────────────────────────────────────────

def _latest_npm(name: str) -> Optional[str]:
    """
    Query the npm registry for the latest stable version.
    https://registry.npmjs.org/<name>
    """
    # Encode scoped packages correctly: @scope/pkg → %40scope%2Fpkg
    encoded = name.replace("@", "%40").replace("/", "%2F")
    data = _http_get_json(f"https://registry.npmjs.org/{encoded}")
    if not data:
        return None

    # dist-tags.latest is the authoritative stable release
    latest = data.get("dist-tags", {}).get("latest")
    if latest and _is_stable(latest):
        return latest

    # Fallback: iterate versions
    versions = list(data.get("versions", {}).keys())
    stable = [v for v in versions if _is_stable(v)]
    if not stable:
        return None

    try:
        from packaging.version import Version
        stable.sort(key=lambda v: Version(v), reverse=True)
        return stable[0]
    except ImportError:
        stable.sort(reverse=True)
        return stable[0]


# ── Maven Central ────────────────────────────────────────────────────────────

def _latest_maven(coordinate: str) -> Optional[str]:
    """
    Query Maven Central Search REST API for the latest stable version.
    coordinate format: "groupId:artifactId"
    https://search.maven.org/solrsearch/select?q=g:<g>+AND+a:<a>&core=gav&rows=1&wt=json
    """
    if ":" not in coordinate:
        return None
    group_id, artifact_id = coordinate.split(":", 1)
    url = (
        "https://search.maven.org/solrsearch/select"
        f"?q=g:{group_id}+AND+a:{artifact_id}&core=gav&rows=20&wt=json"
    )
    data = _http_get_json(url)
    if not data:
        return None

    docs = data.get("response", {}).get("docs", [])
    versions = [d.get("v", "") for d in docs if d.get("v")]
    stable = [v for v in versions if v and _is_stable(v)]
    if not stable:
        return None

    try:
        from packaging.version import Version
        stable.sort(key=lambda v: Version(v), reverse=True)
        return stable[0]
    except ImportError:
        stable.sort(reverse=True)
        return stable[0]


def _latest_nuget(name: str) -> Optional[str]:
    """Query NuGet Search API for the latest stable release of the package."""
    url = f"https://api-v2v3search-0.nuget.org/query?q=packageid:{name.lower()}&prerelease=false"
    data = _http_get_json(url)
    if not data:
        return None
    for item in data.get("data", []):
        if item.get("id", "").lower() == name.lower():
            return item.get("version")
    return None


_latest_version_cache: dict[tuple[str, DependencyEcosystem], Optional[str]] = {}


def get_latest_stable_version(
    name: str,
    ecosystem: DependencyEcosystem,
) -> Optional[str]:
    """
    Query the appropriate registry and return the latest stable version string.
    Caches lookups in-memory to optimize performance.
    """
    cache_key = (name, ecosystem)
    if cache_key in _latest_version_cache:
        return _latest_version_cache[cache_key]

    val = None
    try:
        if ecosystem == DependencyEcosystem.PYTHON:
            val = _latest_pypi(name)
        elif ecosystem == DependencyEcosystem.NODE:
            val = _latest_npm(name)
        elif ecosystem == DependencyEcosystem.JAVA:
            val = _latest_maven(name)
        elif ecosystem == DependencyEcosystem.DOTNET:
            val = _latest_nuget(name)
    except Exception as exc:
        log.warning("Unexpected error resolving %s/%s: %s", ecosystem, name, exc)
        val = None

    _latest_version_cache[cache_key] = val
    return val


