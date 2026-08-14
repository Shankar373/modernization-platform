import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_recommendation_filters_unimplemented_recipes():
    # Target C# project
    req_body = {
        "project_id": "p1",
        "workspace_path": "/tmp/ws",
        "languages": ["csharp"],
        "target_languages": ["csharp"],
        "detected_deps": [],
        "has_tests": False,
        "has_ci": False
    }
    response = client.post("/api/v1/recipes/recommend", json=req_body)
    assert response.status_code == 200
    data = response.json()
    recommended_ids = [r["id"] for r in data["recipes"]]
    
    # Executable recipes should be recommended
    assert "cs-net8-upgrade" in recommended_ids or "cs-nullable-ref" in recommended_ids
    # NOT_IMPLEMENTED C# recipes must NOT be recommended
    assert "cs-sdk-project" not in recommended_ids
    assert "cs-pattern-matching" not in recommended_ids


def test_conflicts_endpoint_blocks_unimplemented_recipes():
    # Attempt to resolve conflicts for a selection containing unimplemented recipe ID
    req_body = {
        "selected_recipe_ids": ["cs-net8-upgrade", "cs-sdk-project"]
    }
    response = client.post("/api/v1/recipes/conflicts", json=req_body)
    assert response.status_code == 200
    data = response.json()
    
    # Conflict Resolution must report has_conflicts = True and include the error
    assert data["has_conflicts"] is True
    errors = data["conflicts"]
    assert len(errors) == 1
    assert errors[0]["recipe_a"] == "cs-sdk-project"
    assert errors[0]["severity"] == "ERROR"
    assert "NOT_IMPLEMENTED" in errors[0]["reason"]


def test_plan_endpoint_rejects_unimplemented_recipes():
    # Generate migration plan with unimplemented recipe ID should raise 400
    req_body = {
        "project_id": "p1",
        "workspace_path": "/tmp/ws",
        "selected_recipe_ids": ["cs-net8-upgrade", "cs-sdk-project"],
        "approved_dep_updates": []
    }
    response = client.post("/api/v1/recipes/plan", json=req_body)
    assert response.status_code == 400
    assert "NOT_IMPLEMENTED" in response.json()["detail"]


def test_execute_endpoint_rejects_unimplemented_recipes():
    # Execute endpoint with unimplemented recipe ID should raise 400
    req_body = {
        "project_id": "p1",
        "workspace_path": "/tmp/ws",
        "recipe_ids": ["cs-net8-upgrade", "cs-sdk-project"],
        "dry_run": False
    }
    response = client.post("/api/v1/recipes/execute", json=req_body)
    assert response.status_code == 400
    assert "NOT_IMPLEMENTED" in response.json()["detail"]
