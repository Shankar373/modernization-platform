"""
Recipe Catalog, AI Recommendation, Conflict Detection, and Migration Plan API

Recipes are atomic, composable transformation units. This service:
  - Maintains a catalog of available recipes per language/framework
  - Recommends recipes based on the project profile (rule-based scoring)
  - Detects conflicts between selected recipes
  - Generates a topologically-ordered Migration Plan
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()

# ── Recipe Catalog ─────────────────────────────────────────────────────────────

RECIPE_CATALOG: List[Dict[str, Any]] = [
    # ── Python ────────────────────────────────────────────────────────────────
    {
        "id": "py-ruff-format",
        "name": "Ruff: Code Formatting",
        "description": "Format Python code using Ruff — the modern, fast Python formatter (replaces Black/autopep8).",
        "language": "python", "category": "style", "complexity": "low",
        "tags": ["formatting", "ruff", "style"],
        "requires": [], "conflicts_with": [],
    },
    {
        "id": "py-ruff-lint",
        "name": "Ruff: Auto-fix Lint Issues",
        "description": "Fix all auto-fixable lint errors (replaces Flake8, Pylint, isort, pyupgrade).",
        "language": "python", "category": "style", "complexity": "low",
        "tags": ["linting", "ruff", "imports"],
        "requires": [], "conflicts_with": [],
    },
    {
        "id": "py-f-strings",
        "name": "Modernize: f-strings",
        "description": "Convert legacy .format() and %-style string formatting to modern f-strings.",
        "language": "python", "category": "upgrade", "complexity": "medium",
        "tags": ["modernize", "syntax", "python3"],
        "requires": [], "conflicts_with": [],
    },
    {
        "id": "py-type-hints",
        "name": "Add Type Hints (PEP 484)",
        "description": "Infer and add type hints to all public function signatures using monkeytype/pytype.",
        "language": "python", "category": "upgrade", "complexity": "high",
        "tags": ["typing", "mypy", "quality"],
        "requires": ["py-ruff-lint"], "conflicts_with": [],
    },
    {
        "id": "py-pathlib",
        "name": "Modernize: pathlib",
        "description": "Replace os.path calls with pathlib.Path for modern, platform-safe path handling.",
        "language": "python", "category": "upgrade", "complexity": "medium",
        "tags": ["modernize", "pathlib", "python3"],
        "requires": [], "conflicts_with": [],
    },
    {
        "id": "py-walrus",
        "name": "Modernize: Walrus Operator (:=)",
        "description": "Use the assignment expression (walrus) operator where it simplifies code (Python 3.8+).",
        "language": "python", "category": "upgrade", "complexity": "medium",
        "tags": ["python38", "syntax", "modernize"],
        "requires": [], "conflicts_with": [],
    },
    # ── Java ──────────────────────────────────────────────────────────────────
    {
        "id": "java-javax-to-jakarta",
        "name": "javax.* → jakarta.* Migration",
        "description": "Rename all javax.* imports/annotations to jakarta.* for Jakarta EE 9+ / Spring Boot 3.",
        "language": "java", "category": "upgrade", "complexity": "medium",
        "tags": ["jakarta", "spring-boot-3", "java17"],
        "requires": [], "conflicts_with": [],
    },
    {
        "id": "java-spring-boot-3",
        "name": "Spring Boot 2 → 3 Migration",
        "description": "Full Spring Boot 2.x to 3.x migration including API changes, pom.xml, and configuration.",
        "language": "java", "category": "upgrade", "complexity": "high",
        "tags": ["spring-boot", "java17", "upgrade"],
        "requires": ["java-javax-to-jakarta"], "conflicts_with": [],
    },
    {
        "id": "java-junit5",
        "name": "JUnit 4 → JUnit 5 Migration",
        "description": "Migrate test classes: annotations (@Test, @Before, @After), assertions, and runners.",
        "language": "java", "category": "upgrade", "complexity": "medium",
        "tags": ["testing", "junit5", "upgrade"],
        "requires": [], "conflicts_with": [],
    },
    {
        "id": "java-var-keyword",
        "name": "Local Variable Type Inference (var)",
        "description": "Replace verbose explicit local variable declarations with `var` (Java 10+).",
        "language": "java", "category": "style", "complexity": "low",
        "tags": ["java10", "var", "style"],
        "requires": [], "conflicts_with": [],
    },
    {
        "id": "java-records",
        "name": "Convert DTOs to Records (Java 16+)",
        "description": "Replace boilerplate data classes (POJO/DTO) with Java record types.",
        "language": "java", "category": "upgrade", "complexity": "medium",
        "tags": ["java16", "records", "modernize"],
        "requires": [], "conflicts_with": [],
    },
    {
        "id": "java-text-blocks",
        "name": "Use Text Blocks (Java 13+)",
        "description": "Replace multi-line string concatenation with Java text blocks.",
        "language": "java", "category": "style", "complexity": "low",
        "tags": ["java13", "text-blocks", "style"],
        "requires": [], "conflicts_with": [],
    },
    # ── JavaScript / TypeScript ────────────────────────────────────────────────
    {
        "id": "js-esm",
        "name": "CommonJS → ES Modules (ESM)",
        "description": "Migrate require() / module.exports to ES module import/export syntax.",
        "language": "javascript", "category": "upgrade", "complexity": "medium",
        "tags": ["esm", "modules", "modernize"],
        "requires": [], "conflicts_with": [],
    },
    {
        "id": "js-optional-chaining",
        "name": "Optional Chaining & Nullish Coalescing",
        "description": "Replace verbose null/undefined checks with ?. and ?? operators.",
        "language": "javascript", "category": "style", "complexity": "low",
        "tags": ["es2020", "syntax", "modernize"],
        "requires": [], "conflicts_with": [],
    },
    {
        "id": "ts-strict-mode",
        "name": "TypeScript Strict Mode",
        "description": "Enable strict: true in tsconfig.json and fix resulting type errors.",
        "language": "typescript", "category": "upgrade", "complexity": "high",
        "tags": ["typescript", "strict", "quality"],
        "requires": [], "conflicts_with": [],
    },
    {
        "id": "ts-no-any",
        "name": "Replace 'any' with Specific Types",
        "description": "Identify all `any` annotations and replace with proper TypeScript types.",
        "language": "typescript", "category": "upgrade", "complexity": "high",
        "tags": ["typescript", "types", "quality"],
        "requires": ["ts-strict-mode"], "conflicts_with": [],
    },
    # ── Security ──────────────────────────────────────────────────────────────
    {
        "id": "sec-dep-audit",
        "name": "Dependency Security Audit",
        "description": "Scan all dependencies for known CVEs and apply safe patch upgrades.",
        "language": "all", "category": "security", "complexity": "medium",
        "tags": ["security", "cve", "audit"],
        "requires": [], "conflicts_with": [],
    },
    {
        "id": "sec-secrets-scan",
        "name": "Secrets & Credential Detection",
        "description": "Scan for accidentally committed secrets (API keys, passwords, tokens) using gitleaks patterns.",
        "language": "all", "category": "security", "complexity": "low",
        "tags": ["security", "secrets", "git"],
        "requires": [], "conflicts_with": [],
    },
    # ── General ───────────────────────────────────────────────────────────────
    {
        "id": "gen-gitignore",
        "name": "Update .gitignore",
        "description": "Update .gitignore with modern, comprehensive patterns for detected tools and languages.",
        "language": "all", "category": "style", "complexity": "low",
        "tags": ["git", "gitignore", "general"],
        "requires": [], "conflicts_with": [],
    },
    {
        "id": "gen-editorconfig",
        "name": "Add/Update .editorconfig",
        "description": "Standardize indentation, line endings, and character encoding across the project.",
        "language": "all", "category": "style", "complexity": "low",
        "tags": ["editorconfig", "style", "general"],
        "requires": [], "conflicts_with": [],
    },
    {
        "id": "gen-ci-pipeline",
        "name": "Generate CI/CD Pipeline",
        "description": "Generate a GitHub Actions / GitLab CI pipeline for build, test, and lint automation.",
        "language": "all", "category": "upgrade", "complexity": "medium",
        "tags": ["ci", "cd", "automation", "devops"],
        "requires": [], "conflicts_with": [],
    },
]

_CATALOG_BY_ID: Dict[str, Dict] = {r["id"]: r for r in RECIPE_CATALOG}


# ── Request/Response Models ────────────────────────────────────────────────────

class RecommendRequest(BaseModel):
    project_id: str
    workspace_path: str
    languages: List[str] = Field(default_factory=list)
    frameworks: List[str] = Field(default_factory=list)
    detected_deps: List[str] = Field(default_factory=list)
    has_tests: bool = False
    has_ci: bool = False


class ConflictsRequest(BaseModel):
    selected_recipe_ids: List[str]


class PlanRequest(BaseModel):
    project_id: str
    workspace_path: str
    selected_recipe_ids: List[str]
    approved_dep_updates: List[Dict[str, Any]] = Field(default_factory=list)


# ── Scoring / AI Recommendation Logic ─────────────────────────────────────────

def _score_recipe(recipe: Dict, req: RecommendRequest) -> int:
    score = 0
    langs_lower = [l.lower() for l in req.languages]
    frameworks_lower = [f.lower() for f in req.frameworks]

    # Language match
    if recipe["language"] == "all":
        score += 6
    elif recipe["language"] in langs_lower:
        score += 12

    # Framework-specific boost
    tags = recipe.get("tags", [])
    for fw in frameworks_lower:
        if any(fw in t for t in tags):
            score += 8

    # Category urgency
    score += {"security": 10, "upgrade": 7, "performance": 6, "style": 4}.get(recipe["category"], 0)

    # Complexity penalty (prefer lower-complexity first)
    score -= {"low": 0, "medium": 2, "high": 4}.get(recipe.get("complexity", "medium"), 2)

    # Boost if dependency was detected
    for dep in req.detected_deps:
        if any(dep.lower() in t for t in tags):
            score += 5

    # Test bonus
    if req.has_tests and any("test" in t for t in tags):
        score += 3

    # CI bonus
    if not req.has_ci and "ci" in tags:
        score += 6

    return score


def _resolve_execution_order(recipe_ids: List[str]) -> List[str]:
    """Topologically sort recipes by their `requires` dependencies."""
    resolved: List[str] = []
    visited: set = set()

    def visit(rid: str):
        if rid in visited:
            return
        visited.add(rid)
        recipe = _CATALOG_BY_ID.get(rid)
        if recipe:
            for dep in recipe.get("requires", []):
                if dep in {r for r in recipe_ids}:
                    visit(dep)
        resolved.append(rid)

    for rid in recipe_ids:
        visit(rid)
    return resolved


def _detect_conflicts(recipe_ids: List[str]) -> List[Dict]:
    conflicts = []
    for rid in recipe_ids:
        recipe = _CATALOG_BY_ID.get(rid)
        if not recipe:
            continue
        for conflicting_id in recipe.get("conflicts_with", []):
            if conflicting_id in recipe_ids:
                conflicts.append({
                    "recipe_a": rid,
                    "recipe_b": conflicting_id,
                    "severity": "ERROR",
                    "reason": f"'{recipe['name']}' and '{_CATALOG_BY_ID.get(conflicting_id, {}).get('name', conflicting_id)}' cannot run together.",
                    "resolution": f"Remove either '{rid}' or '{conflicting_id}' from the selection.",
                })
    return conflicts


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/recipes")
async def list_recipes(language: Optional[str] = None):
    """Return the full recipe catalog, optionally filtered by language."""
    catalog = RECIPE_CATALOG
    if language:
        catalog = [r for r in catalog if r["language"] in (language.lower(), "all")]
    return {"recipes": catalog, "total": len(catalog)}


@router.post("/recipes/recommend")
async def recommend_recipes(req: RecommendRequest):
    """
    Return a ranked list of recommended recipes for the project.
    Uses rule-based scoring on languages, frameworks, dependencies, and project structure.
    """
    scored: List[Dict] = []
    for recipe in RECIPE_CATALOG:
        score = _score_recipe(recipe, req)
        if score > 0:
            scored.append({**recipe, "score": score, "recommended": score >= 12})

    scored.sort(key=lambda r: r["score"], reverse=True)

    # Build human-readable reasoning
    reasoning_parts = []
    if req.languages:
        reasoning_parts.append(f"Detected languages: {', '.join(req.languages)}.")
    if req.frameworks:
        reasoning_parts.append(f"Detected frameworks: {', '.join(req.frameworks)}.")
    if not req.has_ci:
        reasoning_parts.append("No CI/CD pipeline detected — CI generation recommended.")
    if not req.has_tests:
        reasoning_parts.append("No test framework detected — test migration recipes ranked lower.")

    return {
        "recipes": scored,
        "recommended_ids": [r["id"] for r in scored if r.get("recommended")],
        "reasoning": " ".join(reasoning_parts) if reasoning_parts else "General best-practice recommendations applied.",
        "total": len(scored),
    }


@router.post("/recipes/conflicts")
async def detect_recipe_conflicts(req: ConflictsRequest):
    """Detect conflicts and compute execution order for the selected recipes."""
    selected = [_CATALOG_BY_ID[rid] for rid in req.selected_recipe_ids if rid in _CATALOG_BY_ID]
    conflicts = _detect_conflicts(req.selected_recipe_ids)
    ordered_ids = _resolve_execution_order(req.selected_recipe_ids)
    ordered = [_CATALOG_BY_ID[rid] for rid in ordered_ids if rid in _CATALOG_BY_ID]

    # Check for missing required recipes and auto-add them
    auto_added: List[str] = []
    all_selected = set(req.selected_recipe_ids)
    for rid in list(all_selected):
        recipe = _CATALOG_BY_ID.get(rid)
        if recipe:
            for req_id in recipe.get("requires", []):
                if req_id not in all_selected and req_id in _CATALOG_BY_ID:
                    auto_added.append(req_id)

    return {
        "conflicts": conflicts,
        "has_conflicts": len(conflicts) > 0,
        "ordered_recipes": ordered,
        "auto_added_recipes": [_CATALOG_BY_ID[rid] for rid in auto_added if rid in _CATALOG_BY_ID],
        "execution_phases": _build_phases(ordered_ids),
    }


def _build_phases(ordered_ids: List[str]) -> List[Dict]:
    """Group recipes into parallel execution phases."""
    phases: List[Dict] = []
    completed: set = set()

    remaining = list(ordered_ids)
    phase_num = 1

    while remaining:
        # Recipes whose all requirements are in completed
        ready = [
            rid for rid in remaining
            if all(req in completed for req in _CATALOG_BY_ID.get(rid, {}).get("requires", []))
        ]
        if not ready:
            ready = remaining[:1]  # avoid infinite loop

        phase_recipes = [_CATALOG_BY_ID[rid] for rid in ready if rid in _CATALOG_BY_ID]
        phases.append({
            "phase": phase_num,
            "label": f"Phase {phase_num}",
            "recipes": phase_recipes,
            "parallel": True,
        })
        completed.update(ready)
        remaining = [r for r in remaining if r not in ready]
        phase_num += 1

    return phases


@router.post("/recipes/plan")
async def generate_migration_plan(req: PlanRequest):
    """Generate the final Migration Plan from selected recipes and approved dependency updates."""
    selected = [_CATALOG_BY_ID[rid] for rid in req.selected_recipe_ids if rid in _CATALOG_BY_ID]
    ordered_ids = _resolve_execution_order(req.selected_recipe_ids)
    phases = _build_phases(ordered_ids)

    total_complexity_score = sum(
        {"low": 1, "medium": 2, "high": 4}.get(r.get("complexity", "medium"), 2)
        for r in selected
    )
    estimated_files = max(5, total_complexity_score * 3 + len(req.approved_dep_updates) * 2)

    plan = {
        "id": f"plan-{req.project_id[:8]}",
        "project_id": req.project_id,
        "workspace_path": req.workspace_path,
        "created_at": __import__("datetime").datetime.now().isoformat(),
        "phases": phases,
        "selected_recipes": selected,
        "dep_updates_count": len(req.approved_dep_updates),
        "approved_dep_updates": req.approved_dep_updates,
        "estimated_files_changed": estimated_files,
        "complexity_score": total_complexity_score,
        "risk_level": "LOW" if total_complexity_score <= 5 else "MEDIUM" if total_complexity_score <= 12 else "HIGH",
        "git_checkpoint_message": (
            f"chore(modernize): migration checkpoint — "
            f"{len(selected)} recipes, {len(req.approved_dep_updates)} dep updates"
        ),
        "summary": (
            f"{len(selected)} recipes across {len(phases)} phases, "
            f"{len(req.approved_dep_updates)} dependency updates, "
            f"~{estimated_files} files estimated."
        ),
    }

    return {"plan": plan}
