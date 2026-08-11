"""
Dynamic rewrite.yml generator for OpenRewrite.

Generates a minimal, targeted rewrite.yml based only on
the recipes selected for this specific migration plan.
Never generates a file with all available recipes.
"""
from pathlib import Path
from typing import Optional

import yaml

from app.adapters.java.recipe_catalog import RecipeCatalog
from app.core.domain.models import MigrationPlan


class RewriteYmlGenerator:
    """
    Generates a rewrite.yml file tailored to the migration plan.
    Only includes the recipes that were dynamically selected.
    """

    def generate(
        self,
        workspace_path: str,
        plan: MigrationPlan,
        output_path: Optional[str] = None,
    ) -> str:
        """
        Generate rewrite.yml and write it to the workspace.
        Returns the path to the generated file.
        """
        catalog = RecipeCatalog()

        # Re-derive the recipe list from the plan's selected capabilities
        recipe_ids = self._get_recipe_ids_from_plan(plan)

        rewrite_config = {
            "type": "specs.openrewrite.org/v1beta/recipe",
            "name": "com.modernization.platform.MigrationRecipe",
            "displayName": f"Enterprise Migration Plan — {plan.plan_id[:8]}",
            "description": (
                f"Auto-generated migration recipe for plan {plan.plan_id}. "
                f"Profile: {plan.profile.value}. "
                f"Targets: {[t.target_version for t in plan.targets]}"
            ),
            "recipeList": recipe_ids,
        }

        if output_path is None:
            output_path = str(Path(workspace_path) / "rewrite.yml")

        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(rewrite_config, f, default_flow_style=False, sort_keys=False)

        return output_path

    def _get_recipe_ids_from_plan(self, plan: MigrationPlan) -> list:
        """Map plan step names back to OpenRewrite recipe class names."""
        from app.adapters.java.recipe_catalog import _RECIPE_CATALOG
        recipe_map = {r["capability"]: r["openrewrite_recipe"] for r in _RECIPE_CATALOG}

        ids = []
        seen = set()
        for step in plan.steps:
            recipe_class = recipe_map.get(step.capability)
            if recipe_class and recipe_class not in seen:
                ids.append(recipe_class)
                seen.add(recipe_class)
        return ids
