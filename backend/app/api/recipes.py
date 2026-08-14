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
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.recipes.executor import get_executor_help, run_recipe

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
        "min_version": None, "max_version": None,
        "priority": 1, "risk": "LOW", "estimated_impact": "Medium formatting standardizations"
    },
    {
        "id": "py-ruff-lint",
        "name": "Ruff: Auto-fix Lint Issues",
        "description": "Fix all auto-fixable lint errors (replaces Flake8, Pylint, isort, pyupgrade).",
        "language": "python", "category": "style", "complexity": "low",
        "tags": ["linting", "ruff", "imports"],
        "requires": [], "conflicts_with": [],
        "min_version": None, "max_version": None,
        "priority": 2, "risk": "LOW", "estimated_impact": "Clean unused imports and common syntax issues"
    },
    {
        "id": "py-f-strings",
        "name": "Modernize: f-strings",
        "description": "Convert legacy .format() and %-style string formatting to modern f-strings.",
        "language": "python", "category": "upgrade", "complexity": "medium",
        "tags": ["modernize", "syntax", "python3"],
        "requires": [], "conflicts_with": [],
        "min_version": "3.6", "max_version": None,
        "priority": 3, "risk": "LOW", "estimated_impact": "Improve string template performance and readability"
    },
    {
        "id": "py-type-hints",
        "name": "Add Type Hints (PEP 484)",
        "description": "Infer and add type hints to all public function signatures using monkeytype/pytype.",
        "language": "python", "category": "upgrade", "complexity": "high",
        "tags": ["typing", "mypy", "quality"],
        "requires": ["py-ruff-lint"], "conflicts_with": [],
        "min_version": "3.5", "max_version": None,
        "priority": 4, "risk": "MEDIUM", "estimated_impact": "Increase code safety and autocompletion mappings"
    },
    {
        "id": "py-pathlib",
        "name": "Modernize: pathlib",
        "description": "Replace os.path calls with pathlib.Path for modern, platform-safe path handling.",
        "language": "python", "category": "upgrade", "complexity": "medium",
        "tags": ["modernize", "pathlib", "python3"],
        "requires": [], "conflicts_with": [],
        "min_version": "3.4", "max_version": None,
        "priority": 3, "risk": "LOW", "estimated_impact": "Platform-safe OOP directory syntax structures"
    },
    {
        "id": "py-walrus",
        "name": "Modernize: Walrus Operator (:=)",
        "description": "Use the assignment expression (walrus) operator where it simplifies code (Python 3.8+).",
        "language": "python", "category": "upgrade", "complexity": "medium",
        "tags": ["python38", "syntax", "modernize"],
        "requires": [], "conflicts_with": [],
        "min_version": "3.8", "max_version": None,
        "priority": 3, "risk": "LOW", "estimated_impact": "Inline assignment variables syntax patterns"
    },
    # ── Java ──────────────────────────────────────────────────────────────────
    {
        "id": "java-javax-to-jakarta",
        "name": "javax.* → jakarta.* Migration",
        "description": "Rename all javax.* imports/annotations to jakarta.* for Jakarta EE 9+ / Spring Boot 3.",
        "language": "java", "category": "upgrade", "complexity": "medium",
        "tags": ["jakarta", "spring-boot-3", "java17"],
        "requires": [], "conflicts_with": [],
        "min_version": "17", "max_version": None,
        "priority": 10, "risk": "MEDIUM", "estimated_impact": "Mandatory update for modern application containers"
    },
    {
        "id": "java-spring-boot-3",
        "name": "Spring Boot 2 → 3 Migration",
        "description": "Full Spring Boot 2.x to 3.x migration including API changes, pom.xml, and configuration.",
        "language": "java", "category": "upgrade", "complexity": "high",
        "tags": ["spring-boot", "java17", "upgrade"],
        "requires": ["java-javax-to-jakarta"], "conflicts_with": [],
        "min_version": "17", "max_version": None,
        "priority": 12, "risk": "HIGH", "estimated_impact": "Spring framework upgrades and Jakarta compatibility"
    },
    {
        "id": "java-junit5",
        "name": "JUnit 4 → JUnit 5 Migration",
        "description": "Migrate test classes: annotations (@Test, @Before, @After), assertions, and runners.",
        "language": "java", "category": "upgrade", "complexity": "medium",
        "tags": ["testing", "junit5", "upgrade"],
        "requires": [], "conflicts_with": [],
        "min_version": "8", "max_version": None,
        "priority": 5, "risk": "LOW", "estimated_impact": "Standardize test engine configuration models"
    },
    {
        "id": "java-var-keyword",
        "name": "Local Variable Type Inference (var)",
        "description": "Replace verbose explicit local variable declarations with `var` (Java 10+).",
        "language": "java", "category": "style", "complexity": "low",
        "tags": ["java10", "var", "style"],
        "requires": [], "conflicts_with": [],
        "min_version": "10", "max_version": None,
        "priority": 1, "risk": "LOW", "estimated_impact": "Reduce type boilerplate and increase readability"
    },
    {
        "id": "java-records",
        "name": "Convert DTOs to Records (Java 16+)",
        "description": "Replace boilerplate data classes (POJO/DTO) with Java record types.",
        "language": "java", "category": "upgrade", "complexity": "medium",
        "tags": ["java16", "records", "modernize"],
        "requires": [], "conflicts_with": [],
        "min_version": "16", "max_version": None,
        "priority": 6, "risk": "LOW", "estimated_impact": "Immutable value records and properties standard"
    },
    {
        "id": "java-text-blocks",
        "name": "Use Text Blocks (Java 13+)",
        "description": "Replace multi-line string concatenation with Java text blocks.",
        "language": "java", "category": "style", "complexity": "low",
        "tags": ["java13", "text-blocks", "style"],
        "requires": [], "conflicts_with": [],
        "min_version": "13", "max_version": None,
        "priority": 2, "risk": "LOW", "estimated_impact": "Multi-line literal JSON or SQL syntax simplification"
    },
    # ── JavaScript / TypeScript ────────────────────────────────────────────────
    {
        "id": "js-esm",
        "name": "CommonJS → ES Modules (ESM)",
        "description": "Migrate require() / module.exports to ES module import/export syntax.",
        "language": "javascript", "category": "upgrade", "complexity": "medium",
        "tags": ["esm", "modules", "modernize"],
        "requires": [], "conflicts_with": [],
        "min_version": None, "max_version": None,
        "priority": 5, "risk": "MEDIUM", "estimated_impact": "ES Module standard packaging compatibilities"
    },
    {
        "id": "js-optional-chaining",
        "name": "Optional Chaining & Nullish Coalescing",
        "description": "Replace verbose null/undefined checks with ?. and ?? operators.",
        "language": "javascript", "category": "style", "complexity": "low",
        "tags": ["es2020", "syntax", "modernize"],
        "requires": [], "conflicts_with": [],
        "min_version": None, "max_version": None,
        "priority": 1, "risk": "LOW", "estimated_impact": "Short-circuit undefined properties accesses safely"
    },
    {
        "id": "ts-strict-mode",
        "name": "TypeScript Strict Mode",
        "description": "Enable strict: true in tsconfig.json and fix resulting type errors.",
        "language": "typescript", "category": "upgrade", "complexity": "high",
        "tags": ["typescript", "strict", "quality"],
        "requires": [], "conflicts_with": [],
        "min_version": None, "max_version": None,
        "priority": 8, "risk": "MEDIUM", "estimated_impact": "Enforce type compiler safety gates checks"
    },
    {
        "id": "ts-no-any",
        "name": "Replace 'any' with Specific Types",
        "description": "Identify all `any` annotations and replace with proper TypeScript types.",
        "language": "typescript", "category": "upgrade", "complexity": "high",
        "tags": ["typescript", "types", "quality"],
        "requires": ["ts-strict-mode"], "conflicts_with": [],
        "min_version": None, "max_version": None,
        "priority": 9, "risk": "HIGH", "estimated_impact": "Eliminate dynamic typing bypass behaviors"
    },
    # ── Security ──────────────────────────────────────────────────────────────
    {
        "id": "sec-dep-audit",
        "name": "Dependency Security Audit",
        "description": "Scan all dependencies for known CVEs and apply safe patch upgrades.",
        "language": "all", "category": "security", "complexity": "medium",
        "tags": ["security", "cve", "audit"],
        "requires": [], "conflicts_with": [],
        "min_version": None, "max_version": None,
        "priority": 15, "risk": "LOW", "estimated_impact": "Secure codebase components vulnerabilities"
    },
    {
        "id": "sec-secrets-scan",
        "name": "Secrets & Credential Detection",
        "description": "Scan for accidentally committed secrets (API keys, passwords, tokens) using gitleaks patterns.",
        "language": "all", "category": "security", "complexity": "low",
        "tags": ["security", "secrets", "git"],
        "requires": [], "conflicts_with": [],
        "min_version": None, "max_version": None,
        "priority": 14, "risk": "LOW", "estimated_impact": "Prevent credential compromises leaks"
    },
    # ── General ───────────────────────────────────────────────────────────────
    {
        "id": "gen-gitignore",
        "name": "Update .gitignore",
        "description": "Update .gitignore with modern, comprehensive patterns for detected tools and languages.",
        "language": "all", "category": "style", "complexity": "low",
        "tags": ["git", "gitignore", "general"],
        "requires": [], "conflicts_with": [],
        "min_version": None, "max_version": None,
        "priority": 1, "risk": "LOW", "estimated_impact": "Exclude OS/IDE noise from commits logs"
    },
    {
        "id": "gen-editorconfig",
        "name": "Add/Update .editorconfig",
        "description": "Standardize indentation, line endings, and character encoding across the project.",
        "language": "all", "category": "style", "complexity": "low",
        "tags": ["editorconfig", "style", "general"],
        "requires": [], "conflicts_with": [],
        "min_version": None, "max_version": None,
        "priority": 1, "risk": "LOW", "estimated_impact": "Unify IDE visual indentation profiles"
    },
    {
        "id": "gen-ci-pipeline",
        "name": "Generate CI/CD Pipeline",
        "description": "Generate a GitHub Actions / GitLab CI pipeline for build, test, and lint automation.",
        "language": "all", "category": "upgrade", "complexity": "medium",
        "tags": ["ci", "cd", "automation", "devops"],
        "requires": [], "conflicts_with": [],
        "min_version": None, "max_version": None,
        "priority": 5, "risk": "LOW", "estimated_impact": "Automate linting and continuous builds tests"
    },
    # ── C# / .NET ─────────────────────────────────────────────────────────────
    {
        "id": "cs-nullable-ref",
        "name": "Enable Nullable Reference Types",
        "description": "Enable <Nullable>enable</Nullable> in .csproj and annotate all reference types. Roslyn flow analysis eliminates null dereference bugs at compile time.",
        "language": "csharp", "category": "upgrade", "complexity": "medium",
        "tags": ["nullable", "dotnet", "csharp", "safety"],
        "requires": [], "conflicts_with": [],
        "min_version": "8.0", "max_version": None,
        "priority": 8, "risk": "MEDIUM", "estimated_impact": "Eliminate null-reference runtime exceptions via Roslyn static analysis"
    },
    {
        "id": "cs-net6-upgrade",
        "name": ".NET Framework → .NET 6/8 Upgrade",
        "description": "Migrate TargetFramework from net4x / netstandard2.0 to net6.0 or net8.0. Updates System.* namespace usage, removes deprecated APIs, and migrates app host configuration.",
        "language": "csharp", "category": "upgrade", "complexity": "high",
        "tags": ["dotnet", "csharp", "upgrade", "net6", "net8", "migration"],
        "requires": [], "conflicts_with": [],
        "min_version": None, "max_version": None,
        "priority": 15, "risk": "HIGH", "estimated_impact": "Long-term support framework and performance improvements (AOT eligible)"
    },
    {
        "id": "cs-var-keyword",
        "name": "Local Variable Type Inference (var)",
        "description": "Replace verbose explicit local variable declarations with var where the type is obvious. Improves readability without losing type safety.",
        "language": "csharp", "category": "style", "complexity": "low",
        "tags": ["style", "csharp", "dotnet", "var"],
        "requires": [], "conflicts_with": [],
        "min_version": "3.0", "max_version": None,
        "priority": 2, "risk": "LOW", "estimated_impact": "Reduce boilerplate type annotations in local scopes"
    },
    {
        "id": "cs-async-await",
        "name": "Synchronous → async/await Migration",
        "description": "Convert blocking synchronous I/O patterns (Thread.Sleep, .Result, .Wait()) to async/await with Task-based asynchronous pattern (TAP). Improves throughput under load.",
        "language": "csharp", "category": "upgrade", "complexity": "high",
        "tags": ["async", "await", "dotnet", "csharp", "performance"],
        "requires": [], "conflicts_with": [],
        "min_version": "5.0", "max_version": None,
        "priority": 10, "risk": "HIGH", "estimated_impact": "Thread pool efficiency and I/O-bound scalability improvements"
    },
    {
        "id": "cs-dependency-injection",
        "name": "Manual DI → Microsoft.Extensions.DI",
        "description": "Migrate from manual service instantiation / static service locator patterns to Microsoft.Extensions.DependencyInjection. Register services in IServiceCollection, use constructor injection throughout.",
        "language": "csharp", "category": "upgrade", "complexity": "medium",
        "tags": ["di", "dependency-injection", "aspnet", "csharp", "dotnet"],
        "requires": [], "conflicts_with": [],
        "min_version": None, "max_version": None,
        "priority": 9, "risk": "MEDIUM", "estimated_impact": "Loosely coupled, testable service architecture for ASP.NET Core"
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
    source_version: Optional[str] = None
    target_version: Optional[str] = None


class ConflictsRequest(BaseModel):
    selected_recipe_ids: List[str]


class PlanRequest(BaseModel):
    project_id: str
    workspace_path: str
    selected_recipe_ids: List[str]
    approved_dep_updates: List[Dict[str, Any]] = Field(default_factory=list)
    source_version: Optional[str] = None
    target_version: Optional[str] = None


# ── Helper Functions ──────────────────────────────────────────────────────────

def _version_parse(v_str: Optional[str]) -> tuple:
    """Helper to parse a version string into a tuple of ints for comparisons."""
    if not v_str:
        return (0,)
    cleaned = re.sub(r"[^0-9.]", "", v_str)
    try:
        return tuple(int(x) for x in cleaned.split(".") if x)
    except ValueError:
        return (0,)


def _is_version_compatible(recipe: Dict, source_version: Optional[str], target_version: Optional[str]) -> bool:
    """Validate if the recipe starting version boundary matches the project source environment."""
    min_v = recipe.get("min_version")
    max_v = recipe.get("max_version")

    if not min_v and not max_v:
        return True

    parsed_source = _version_parse(source_version)
    parsed_target = _version_parse(target_version)

    if min_v:
        parsed_min = _version_parse(min_v)
        # Target must at least support this minimum version
        if target_version and parsed_target < parsed_min:
            return False
        # If source is explicitly below the minimum, it might be applicable ONLY if we are migrating up
        if source_version and parsed_source < parsed_min:
            if not (target_version and parsed_target >= parsed_min):
                return False

    if max_v:
        parsed_max = _version_parse(max_v)
        if source_version and parsed_source > parsed_max:
            return False

    return True


# ── Scoring / AI Recommendation Logic ─────────────────────────────────────────

def _score_recipe(recipe: Dict, req: RecommendRequest) -> tuple[int, List[str]]:
    score = 0
    reasons = []
    langs_lower = [l.lower() for l in req.languages]
    frameworks_lower = [f.lower() for f in req.frameworks]

    # Language match
    if recipe["language"] == "all":
        score += 6
        reasons.append("Recipe is generic and applies to all codebases")
    elif recipe["language"] in langs_lower:
        score += 12
        reasons.append(f"Project language matches: {recipe['language']}")

    # Framework-specific boost
    tags = recipe.get("tags", [])
    for fw in frameworks_lower:
        if any(fw in t for t in tags):
            score += 8
            reasons.append(f"Framework support match: {fw}")

    # Category urgency
    cat_boost = {"security": 10, "upgrade": 7, "performance": 6, "style": 4}.get(recipe["category"], 0)
    score += cat_boost
    if cat_boost > 0:
        reasons.append(f"Category urgency priority: {recipe['category'].upper()} (+{cat_boost})")

    # Complexity penalty
    penalty = {"low": 0, "medium": 2, "high": 4}.get(recipe.get("complexity", "medium"), 2)
    score -= penalty
    if penalty > 0:
        reasons.append(f"Complexity overhead correction ({recipe['complexity'].upper()} penalty: -{penalty})")

    # Dependency boosts
    for dep in req.detected_deps:
        if any(dep.lower() in t for t in tags):
            score += 5
            reasons.append(f"Boost from detected dependency parameter: {dep}")

    # Test integrations
    if req.has_tests and any("test" in t for t in tags):
        score += 3
        reasons.append("Test automation framework boost")

    # CI checks
    if not req.has_ci and "ci" in tags:
        score += 6
        reasons.append("Generate build lifecycle pipeline triggers")

    return score, reasons


def _resolve_execution_order(recipe_ids: List[str]) -> List[str]:
    """Topologically sort recipes by their `requires` dependencies, supporting transitive resolution and cycles detection."""
    resolved: List[str] = []
    visited: set = set()
    visiting: set = set()

    # 1. Gather all transitive dependencies automatically
    full_selection = set(recipe_ids)
    def gather_dependencies(rid: str):
        recipe = _CATALOG_BY_ID.get(rid)
        if recipe:
            for req_id in recipe.get("requires", []):
                if req_id not in full_selection and req_id in _CATALOG_BY_ID:
                    full_selection.add(req_id)
                    gather_dependencies(req_id)

    for rid in list(recipe_ids):
        gather_dependencies(rid)

    # 2. Topological sort with DFS cycle detection
    def visit(rid: str):
        if rid in visiting:
            cycle_list = list(visiting) + [rid]
            raise HTTPException(
                status_code=400,
                detail={
                    "type": "RECIPE_DEPENDENCY_CYCLE",
                    "recipes": cycle_list
                }
            )
        if rid in visited:
            return

        visiting.add(rid)
        recipe = _CATALOG_BY_ID.get(rid)
        if recipe:
            for dep in recipe.get("requires", []):
                if dep in full_selection:
                    visit(dep)
        visiting.remove(rid)
        visited.add(rid)
        resolved.append(rid)

    for rid in sorted(full_selection):  # Sort for determinism
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
    Uses rule-based scoring on languages, frameworks, dependencies, and version compatibility gates.
    """
    from app.capabilities.registry import registry
    from app.core.domain.models import CapabilityStatus

    # Only recommend recipes whose language is part of the detected project
    # profile (plus generic language-agnostic recipes). This prevents, e.g.,
    # Python/Java/JS recipes from being recommended for a C# workspace.
    detected_langs = {l.strip().lower() for l in req.languages if l and l.strip()}

    scored: List[Dict] = []
    for recipe in RECIPE_CATALOG:
        is_applicable = _is_version_compatible(recipe, req.source_version, req.target_version)
        if not is_applicable:
            continue

        lang = recipe.get("language") or "all"
        # Language-specific recipes require a matching detected language. If no
        # languages were detected at all, only generic (language="all") recipes
        # are eligible — nothing specific to an untargeted language is surfaced.
        if lang != "all" and lang not in detected_langs:
            continue

        # Check tool availability for this language in registry
        is_tool_available = True
        if lang and lang != "all":
            caps = registry.get_for_language(lang)
            is_tool_available = bool(caps and any(
                c.status in (CapabilityStatus.AVAILABLE, CapabilityStatus.PARTIAL)
                for c in caps
            ))

        if not is_tool_available:
            continue

        score, reasons = _score_recipe(recipe, req)
        is_recommended = score >= 12
        
        scored.append({
            **recipe,
            "score": score,
            "applicable": True,
            "recommended": is_recommended,
            "reasons": reasons
        })

    scored.sort(key=lambda r: (-r["score"], r["id"]))

    reasoning_parts = []
    if req.languages:
        reasoning_parts.append(f"Detected languages: {', '.join(req.languages)}.")
        if detected_langs:
            reasoning_parts.append(
                f"Recommendations restricted to recipes targeting {', '.join(sorted(detected_langs))} or generic recipes."
            )
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
    conflicts = _detect_conflicts(req.selected_recipe_ids)
    ordered_ids = _resolve_execution_order(req.selected_recipe_ids)
    ordered = [_CATALOG_BY_ID[rid] for rid in ordered_ids if rid in _CATALOG_BY_ID]

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
        ready = [
            rid for rid in remaining
            if all(req in completed for req in _CATALOG_BY_ID.get(rid, {}).get("requires", []))
        ]
        if not ready:
            ready = remaining[:1]

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
    ordered_ids = _resolve_execution_order(req.selected_recipe_ids)
    selected = [_CATALOG_BY_ID[rid] for rid in ordered_ids if rid in _CATALOG_BY_ID]
    phases = _build_phases(ordered_ids)

    for r in selected:
        if not _is_version_compatible(r, req.source_version, req.target_version):
            raise HTTPException(
                status_code=400,
                detail=f"Selected recipe '{r['name']}' requires version constraints that are incompatible with target/source settings."
            )

    total_complexity_score = sum(
        {"low": 1, "medium": 2, "high": 4}.get(r.get("complexity", "medium"), 2)
        for r in selected
    )
    estimated_files = max(5, total_complexity_score * 3 + len(req.approved_dep_updates) * 2)

    steps = []
    for index, rid in enumerate(ordered_ids, 1):
        r = _CATALOG_BY_ID.get(rid)
        if r:
            steps.append({
                "recipe": r["name"],
                "order": index,
                "reason": r["description"],
                "dependencies": r.get("requires", []),
                "risk": r.get("risk", "LOW"),
                "expected_impact": r.get("estimated_impact", "Standard system refactoring")
            })

    plan = {
        "id": f"plan-{req.project_id[:8]}",
        "project_id": req.project_id,
        "workspace_path": req.workspace_path,
        "created_at": __import__("datetime").datetime.now().isoformat(),
        "phases": phases,
        "steps": steps,
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


class ExecuteRequest(BaseModel):
    project_id: str
    workspace_path: str
    recipe_ids: List[str] = Field(default_factory=list)
    dry_run: bool = False


@router.post("/recipes/execute")
async def execute_recipes(req: ExecuteRequest):
    """
    Execute the selected recipes for real: applies transformations to the
    workspace and returns per-recipe changed files + security findings.
    Use dry_run=true to preview without modifying files.
    """
    if not req.recipe_ids:
        return {"recipes": [], "summary": "No recipes selected."}

    results = []
    implemented = 0
    for rid in req.recipe_ids:
        recipe = _CATALOG_BY_ID.get(rid)
        name = recipe["name"] if recipe else rid
        result = run_recipe(rid, name, req.workspace_path, dry_run=req.dry_run)
        if result.status == "EXECUTED":
            implemented += 1
        results.append(result.to_dict())

    total_files_changed = sum(len(r["changed_files"]) for r in results)
    total_findings = sum(len(r["findings"]) for r in results)
    failed = [r["recipe_id"] for r in results if r["status"] == "FAILED"]
    not_impl = [r["recipe_id"] for r in results if r["status"] == "NOT_IMPLEMENTED"]

    return {
        "recipes": results,
        "mode": "dry-run" if req.dry_run else "apply",
        "recipes_executed": implemented,
        "recipes_not_implemented": not_impl,
        "recipes_failed": failed,
        "files_changed": total_files_changed,
        "findings_count": total_findings,
        "implemented_recipe_ids": sorted(get_executor_help()),
        "summary": (
            f"{implemented} recipe(s) executed, {len(not_impl)} not implemented, "
            f"{len(failed)} failed. {total_files_changed} file(s) affected, "
            f"{total_findings} security finding(s)."
        ),
    }
