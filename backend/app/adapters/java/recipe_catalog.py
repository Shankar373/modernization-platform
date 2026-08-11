"""
OpenRewrite Recipe Catalog — controlled recipe selection.

Recipes are selected dynamically based on:
  source_version + target_version + detected frameworks + dependencies + migration_profile.

DO NOT dump all OpenRewrite recipes into rewrite.yml.
"""
from typing import List, Dict, Any

from app.core.domain.models import MigrationProfile


# ── Controlled Recipe Catalog ─────────────────────────────────────────────────
# Each entry defines when a recipe applies and its risk profile.

_RECIPE_CATALOG: List[Dict[str, Any]] = [
    # ── Java version upgrades ─────────────────────────────────────────────────
    {
        "id": "java-8-to-11",
        "name": "Upgrade to Java 11",
        "description": "Migrate Java 8 source compatibility to Java 11",
        "openrewrite_recipe": "org.openrewrite.java.migrate.Java8toJava11",
        "capability": "java-8-to-17",
        "applies_when": {
            "source_versions": ["8", "1.8"],
            "target_versions": ["11", "17", "21"],
        },
        "risk": "MEDIUM",
        "estimated_files": 0,
        "is_reversible": True,
        "profiles": [MigrationProfile.CONSERVATIVE, MigrationProfile.STANDARD, MigrationProfile.AGGRESSIVE],
    },
    {
        "id": "java-11-to-17",
        "name": "Upgrade to Java 17",
        "description": "Migrate Java 11 to Java 17 LTS",
        "openrewrite_recipe": "org.openrewrite.java.migrate.UpgradeToJava17",
        "capability": "java-11-to-17",
        "applies_when": {
            "source_versions": ["8", "1.8", "11"],
            "target_versions": ["17", "21"],
        },
        "risk": "MEDIUM",
        "estimated_files": 0,
        "is_reversible": True,
        "profiles": [MigrationProfile.CONSERVATIVE, MigrationProfile.STANDARD, MigrationProfile.AGGRESSIVE],
    },
    {
        "id": "java-17-to-21",
        "name": "Upgrade to Java 21",
        "description": "Migrate to Java 21 LTS",
        "openrewrite_recipe": "org.openrewrite.java.migrate.UpgradeToJava21",
        "capability": "java-11-to-21",
        "applies_when": {
            "source_versions": ["8", "1.8", "11", "17"],
            "target_versions": ["21"],
        },
        "risk": "HIGH",
        "estimated_files": 0,
        "is_reversible": True,
        "profiles": [MigrationProfile.STANDARD, MigrationProfile.AGGRESSIVE],
    },
    # ── javax → jakarta namespace migration ───────────────────────────────────
    {
        "id": "javax-to-jakarta",
        "name": "Migrate javax to jakarta namespace",
        "description": "Replace javax.* imports with jakarta.* (required for Spring Boot 3.x / Java EE 10)",
        "openrewrite_recipe": "org.openrewrite.java.migrate.jakarta.JavaxMigrationToJakarta",
        "capability": "javax-to-jakarta",
        "applies_when": {
            "target_versions": ["17", "21"],
            "frameworks_include": ["spring boot 3", "jakarta"],
        },
        "risk": "MEDIUM",
        "estimated_files": 0,
        "is_reversible": True,
        "profiles": [MigrationProfile.CONSERVATIVE, MigrationProfile.STANDARD, MigrationProfile.AGGRESSIVE],
    },
    # ── Spring Boot migrations ────────────────────────────────────────────────
    {
        "id": "spring-boot-2x",
        "name": "Upgrade Spring Boot to 2.x",
        "description": "Migrate Spring Boot 1.x to 2.x",
        "openrewrite_recipe": "org.openrewrite.java.spring.boot2.SpringBoot1To2Migration",
        "capability": "spring-boot-1x-to-2x",
        "applies_when": {
            "frameworks_include": ["spring boot 1", "spring boot 1.x"],
        },
        "risk": "MEDIUM",
        "estimated_files": 0,
        "is_reversible": True,
        "profiles": [MigrationProfile.CONSERVATIVE, MigrationProfile.STANDARD, MigrationProfile.AGGRESSIVE],
    },
    {
        "id": "spring-boot-3x",
        "name": "Upgrade Spring Boot to 3.x",
        "description": "Migrate Spring Boot 2.x to 3.x (requires Java 17+, jakarta namespace)",
        "openrewrite_recipe": "org.openrewrite.java.spring.boot3.UpgradeSpringBoot_3_0",
        "capability": "spring-boot-2x-to-3x",
        "applies_when": {
            "frameworks_include": ["spring boot 2", "spring boot 2.x"],
            "target_versions": ["17", "21"],
        },
        "risk": "HIGH",
        "estimated_files": 0,
        "is_reversible": False,
        "profiles": [MigrationProfile.STANDARD, MigrationProfile.AGGRESSIVE],
    },
    # ── Dependency updates (Standard/Aggressive only) ─────────────────────────
    {
        "id": "dependency-updates",
        "name": "Update outdated Maven dependencies",
        "description": "Upgrade outdated Maven dependency versions",
        "openrewrite_recipe": "org.openrewrite.maven.UpgradeDependencyVersion",
        "capability": "java-dependency-modernization",
        "applies_when": {},
        "risk": "LOW",
        "estimated_files": 1,
        "is_reversible": True,
        "profiles": [MigrationProfile.STANDARD, MigrationProfile.AGGRESSIVE],
    },
    # ── Code cleanup (Aggressive only) ────────────────────────────────────────
    {
        "id": "common-static-analysis",
        "name": "Common static analysis fixes",
        "description": "Apply common best-practice code fixes",
        "openrewrite_recipe": "org.openrewrite.java.cleanup.CommonStaticAnalysis",
        "capability": "java-dependency-modernization",
        "applies_when": {},
        "risk": "LOW",
        "estimated_files": 0,
        "is_reversible": True,
        "profiles": [MigrationProfile.AGGRESSIVE],
    },
]


class RecipeCatalog:
    """
    Controlled recipe selection engine.

    Selects only the recipes that are applicable to the detected
    source technology, target version, frameworks, and migration profile.

    Never dumps all recipes — only includes what is needed.
    """

    def select_recipes(
        self,
        source_version: str,
        target_version: str,
        frameworks: List[str],
        dependencies: List[str],
        migration_profile: MigrationProfile,
    ) -> List[Dict[str, Any]]:
        selected = []
        norm_source = self._normalize_version(source_version)
        norm_target = self._normalize_version(target_version)
        norm_frameworks = [f.lower() for f in frameworks]

        for recipe in _RECIPE_CATALOG:
            if not self._profile_matches(recipe, migration_profile):
                continue
            if not self._condition_matches(recipe["applies_when"], norm_source, norm_target, norm_frameworks):
                continue
            selected.append(recipe)

        # Deduplicate by id preserving order
        seen = set()
        unique = []
        for r in selected:
            if r["id"] not in seen:
                seen.add(r["id"])
                unique.append(r)
        return unique

    def _normalize_version(self, v: str) -> str:
        return v.strip().lower().replace("1.", "") if v else ""

    def _profile_matches(self, recipe: Dict, profile: MigrationProfile) -> bool:
        return profile in recipe.get("profiles", [])

    def _condition_matches(
        self,
        conditions: Dict,
        source_version: str,
        target_version: str,
        frameworks: List[str],
    ) -> bool:
        if not conditions:
            return True
        if "source_versions" in conditions:
            norm = [self._normalize_version(v) for v in conditions["source_versions"]]
            if source_version not in norm:
                return False
        if "target_versions" in conditions:
            norm = [self._normalize_version(v) for v in conditions["target_versions"]]
            if target_version not in norm:
                return False
        if "frameworks_include" in conditions:
            required = [f.lower() for f in conditions["frameworks_include"]]
            if not any(any(r in fw for fw in frameworks) for r in required):
                return False
        return True

    def get_openrewrite_recipe_ids(self, selected_recipes: List[Dict]) -> List[str]:
        """Return the OpenRewrite recipe class names for rewrite.yml generation."""
        return [r["openrewrite_recipe"] for r in selected_recipes]
