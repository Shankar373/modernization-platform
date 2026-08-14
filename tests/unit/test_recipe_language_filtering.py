"""
Tests for language-aware recipe recommendation.

Verifies that recipes are only recommended when the target language is
actually part of the detected project profile, plus generic (language="all")
recipes.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from app.api.recipes import RecommendRequest, recommend_recipes
from app.capabilities.registry import registry
from app.core.domain.models import CapabilityStatus, MigrationCapability


def _recommend(languages, frameworks=()):
    req = RecommendRequest(
        project_id="p1",
        workspace_path="/tmp/ws",
        languages=languages,
        frameworks=list(frameworks),
        detected_deps=[],
        has_tests=False,
        has_ci=False,
    )
    # Force every language to report an available tool so the language filter
    # (not tool availability) is what the test is exercising.
    with patch.object(registry, "get_for_language") as mock_get:
        mock_get.return_value = [
            MigrationCapability(
                name="fake",
                language="fake",
                provider="fake",
                status=CapabilityStatus.AVAILABLE,
            )
        ]
        return asyncio.run(recommend_recipes(req))


def test_csharp_project_excludes_other_language_recipes():
    result = _recommend(["csharp"])
    ids = {r["id"] for r in result["recipes"]}

    assert any(i.startswith("cs-") for i in ids), "expected C# recipes to be recommended"
    assert not any(i.startswith("py-") for i in ids), "Python recipes must not appear for a C# project"
    assert not any(i.startswith("java-") for i in ids), "Java recipes must not appear for a C# project"
    assert not any(i.startswith("js-") for i in ids), "JS recipes must not appear for a C# project"
    assert not any(i.startswith("ts-") for i in ids), "TS recipes must not appear for a C# project"


def test_python_project_excludes_csharp_recipes():
    result = _recommend(["python"])
    ids = {r["id"] for r in result["recipes"]}

    assert any(i.startswith("py-") for i in ids), "expected Python recipes to be recommended"
    assert not any(i.startswith("cs-") for i in ids), "C# recipes must not appear for a Python project"


def test_generic_all_language_recipes_survive_filtering():
    result = _recommend(["csharp"])
    ids = {r["id"] for r in result["recipes"]}
    assert "sec-secrets-scan" in ids
    assert "gen-gitignore" in ids


def test_csharp_recipes_not_recommended_without_any_language():
    result = _recommend([])
    ids = {r["id"] for r in result["recipes"]}
    assert not any(i.startswith("cs-") for i in ids)
    # Generic recipes are still surfaced when no languages are reported.
    assert "sec-secrets-scan" in ids

def test_csharp_migration_excludes_jsts_even_if_detected():
    result = _recommend(["c#", "javascript", "typescript"])
    ids = {r["id"] for r in result["recipes"]}
    assert any(i.startswith("cs-") for i in ids), "expected C# recipes"
    assert not any(i.startswith("js-") for i in ids), "JS recipes must not appear for a C# migration even if JS was detected"
    assert not any(i.startswith("ts-") for i in ids), "TS recipes must not appear for a C# migration even if TS was detected"


def test_javascript_migration_allows_js():
    result = _recommend(["javascript"])
    ids = {r["id"] for r in result["recipes"]}
    assert any(i.startswith("js-") for i in ids), "expected JS recipes"
    assert not any(i.startswith("cs-") for i in ids), "no C# recipes"


def test_typescript_migration_allows_ts():
    result = _recommend(["typescript"])
    ids = {r["id"] for r in result["recipes"]}
    assert any(i.startswith("ts-") for i in ids), "expected TS recipes"
    assert not any(i.startswith("cs-") for i in ids), "no C# recipes"


def test_mixed_language_migration_allows_both():
    req = RecommendRequest(
        project_id="p1",
        workspace_path="/tmp/ws",
        languages=["c#", "javascript"],
        target_languages=["csharp", "javascript"],
        detected_deps=[],
        has_tests=False,
        has_ci=False,
    )
    with patch.object(registry, "get_for_language") as mock_get:
        mock_get.return_value = [
            MigrationCapability(
                name="fake",
                language="fake",
                provider="fake",
                status=CapabilityStatus.AVAILABLE,
            )
        ]
        result = asyncio.run(recommend_recipes(req))
    ids = {r["id"] for r in result["recipes"]}
    assert any(i.startswith("cs-") for i in ids), "expected C# recipes"
    assert any(i.startswith("js-") for i in ids), "expected JS recipes"


def test_unsupported_connector_excludes_recipe():
    req = RecommendRequest(
        project_id="p1",
        workspace_path="/tmp/ws",
        languages=["csharp"],
        detected_deps=[],
        has_tests=False,
        has_ci=False,
    )
    with patch.object(registry, "get_for_language") as mock_get:
        mock_get.return_value = [
            MigrationCapability(
                name="fake",
                language="fake",
                provider="fake",
                status=CapabilityStatus.NOT_AVAILABLE,
            )
        ]
        result = asyncio.run(recommend_recipes(req))
    ids = {r["id"] for r in result["recipes"]}
    assert not any(i.startswith("cs-") for i in ids), "C# recipes should be excluded if capability is NOT_AVAILABLE"


def test_mixed_language_migration_allows_csharp_and_typescript():
    req = RecommendRequest(
        project_id="p1",
        workspace_path="/tmp/ws",
        languages=["c#", "typescript"],
        target_languages=["csharp", "typescript"],
        detected_deps=[],
        has_tests=False,
        has_ci=False,
    )
    with patch.object(registry, "get_for_language") as mock_get:
        mock_get.return_value = [
            MigrationCapability(
                name="fake",
                language="fake",
                provider="fake",
                status=CapabilityStatus.AVAILABLE,
            )
        ]
        result = asyncio.run(recommend_recipes(req))
    ids = {r["id"] for r in result["recipes"]}
    assert any(i.startswith("cs-") for i in ids), "expected C# recipes"
    assert any(i.startswith("ts-") for i in ids), "expected TS recipes"
