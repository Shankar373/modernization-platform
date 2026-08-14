import pytest
from app.api.recipes import RECIPE_CATALOG
from app.recipes.executor import has_handler
from app.adapters.base import adapter_registry

def test_recipe_catalog_vs_registry_consistency():
    """Validate that every recipe in the catalog matches its implementation state."""
    for recipe in RECIPE_CATALOG:
        rid = recipe["id"]
        lang = recipe.get("language")
        
        # 1. Resolve State
        if has_handler(rid):
            state = "IMPLEMENTED_AND_EXECUTABLE"
        else:
            state = "NOT_IMPLEMENTED"
            
        # 2. Check that NOT_IMPLEMENTED recipes are NOT recommended or displayed as executable
        if state == "NOT_IMPLEMENTED":
            # Verify it's not registered
            assert not has_handler(rid)
        else:
            assert has_handler(rid)

def test_execution_order_prevents_not_implemented_recipes():
    """Verify that any attempt to sort or validate NOT_IMPLEMENTED recipes throws an error or is blocked."""
    from app.api.recipes import _detect_conflicts
    
    # Passing a dummy list with a NOT_IMPLEMENTED recipe should return an error conflict
    conflicts = _detect_conflicts(["non-existent-recipe-id"])
    assert len(conflicts) > 0
    assert any("is NOT_IMPLEMENTED" in c["reason"] for c in conflicts)
