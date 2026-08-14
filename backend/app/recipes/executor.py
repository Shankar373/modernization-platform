"""
Recipe Execution Engine

Turns recipe catalog IDs into real, applied transformations on a workspace.
Each recipe registers a handler that:

  - Executes in dry-run or apply mode
  - Returns structured FileChangeMetadata (with diffs) for every touched file
  - For scan/audit recipes returns findings instead of file diffs

Handlers only rewrite files with conservative, well-tested transformations and
never touch ignored paths (node_modules, .git, venv, dist, etc.).
"""
from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from app.adapters.base import is_ignored_path
from app.core.domain.models import FileChangeMetadata

_MAX_FILE_BYTES = 512 * 1024

_SKIP_DIRS = {"node_modules", ".venv", "venv", "__pycache__", ".git", "dist", "build", ".next", ".vs", ".idea"}


# ── Result containers ──────────────────────────────────────────────────────────

@dataclass
class RecipeFinding:
    """A non-transform finding (e.g. a located secret or an outdated dependency)."""
    file: str
    severity: str                      # LOW | MEDIUM | HIGH | CRITICAL
    message: str
    evidence: str = ""


@dataclass
class RecipeExecutionResult:
    recipe_id: str
    recipe_name: str
    success: bool = True
    status: str = "EXECUTED"           # EXECUTED | FAILED | NOT_APPLICABLE
    changed_files: List[FileChangeMetadata] = field(default_factory=list)
    findings: List[RecipeFinding] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "recipe_id": self.recipe_id,
            "recipe_name": self.recipe_name,
            "success": self.success,
            "status": self.status,
            "changed_files": [f.model_dump() for f in self.changed_files],
            "findings": [
                {"file": f.file, "severity": f.severity, "message": f.message, "evidence": f.evidence}
                for f in self.findings
            ],
            "notes": self.notes,
            "errors": self.errors,
        }


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _iter_files(ws: Path, suffixes: Optional[set[str]] = None) -> List[Path]:
    """Yield candidate files under the workspace, honoring skip dirs and max size."""
    out: List[Path] = []
    for f in ws.rglob("*"):
        if not f.is_file():
            continue
        if is_ignored_path(f):
            continue
        rel = f.relative_to(ws)
        if any(part in _SKIP_DIRS for part in rel.parts):
            continue
        if suffixes and f.suffix.lower() not in suffixes:
            continue
        try:
            if f.stat().st_size > _MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        out.append(f)
    return out


def _build_change(rel: str, before: str, after: str, tool: str, change_type: str, description: str) -> FileChangeMetadata:
    return FileChangeMetadata(
        file=rel,
        status="MODIFIED",
        before_content=before,
        after_content=after,
        diff="".join(difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}")),
        tools=[tool],
        changes=[{"type": change_type, "description": description}],
    )


# ── Handler registry ───────────────────────────────────────────────────────────

Handler = Callable[[Path, bool], RecipeExecutionResult]
_REGISTRY: Dict[str, Handler] = {}


def register(recipe_id: str):
    def decorator(fn: Handler):
        _REGISTRY[recipe_id] = fn
        return fn
    return decorator


def has_handler(recipe_id: str) -> bool:
    return recipe_id in _REGISTRY


def run_recipe(recipe_id: str, recipe_name: str, workspace_path: str, dry_run: bool = False) -> RecipeExecutionResult:
    handler = _REGISTRY.get(recipe_id)
    if not handler:
        return RecipeExecutionResult(
            recipe_id=recipe_id,
            recipe_name=recipe_name,
            status="NOT_IMPLEMENTED",
            notes=[f"No transformation handler registered for '{recipe_id}'."],
        )
    try:
        return handler(Path(workspace_path), dry_run)
    except Exception as exc:  # handler must never crash a batch run
        return RecipeExecutionResult(
            recipe_id=recipe_id,
            recipe_name=recipe_name,
            success=False,
            status="FAILED",
            errors=[str(exc)],
        )


# ── Handlers: JS / TS ──────────────────────────────────────────────────────────

_REQUIRE_PATTERNS = [
    (re.compile(r"^\s*const\s+(\w+)\s*=\s*require\(['\"]([^'\"]+)['\"]\)\s*;?", re.MULTILINE),
     r"import \1 from '\2';"),
    (re.compile(r"^\s*const\s+\{([^}]+)\}\s*=\s*require\(['\"]([^'\"]+)['\"]\)\s*;?", re.MULTILINE),
     lambda m: f"import {{{m.group(1).strip()}}} from '{m.group(2)}';"),
]

_MODULE_EXPORT_DEFAULT = re.compile(r"^\s*module\.exports\s*=\s*(.+?)\s*;?\s*$", re.MULTILINE)
_MODULE_EXPORT_NAMED = re.compile(r"^\s*module\.exports\.(\w+)\s*=\s*(.+?)\s*;?\s*$", re.MULTILINE)
_EXPORTS_NAMED = re.compile(r"^\s*exports\.(\w+)\s*=\s*(.+?)\s*;?\s*$", re.MULTILINE)


def _to_esm(content: str) -> str:
    result = content
    for pat, repl in _REQUIRE_PATTERNS:
        if callable(repl):
            result = pat.sub(repl, result)
        else:
            result = pat.sub(repl, result)

    def _named(m: re.Match) -> str:
        # Only rewrite simple assignments (identifier / literal / member), skip functions/classes
        expr = m.group(2).strip()
        if re.match(r"^[$\w.\][\'\"]+$", expr):
            return f"export const {m.group(1)} = {expr};"
        return m.group(0)

    result = _MODULE_EXPORT_NAMED.sub(_named, result)
    result = _EXPORTS_NAMED.sub(_named, result)
    result = _MODULE_EXPORT_DEFAULT.sub(lambda m: f"export default {m.group(1).strip() or '{}'};" if m.group(
        1).strip() else m.group(0), result)
    return result


@register("js-esm")
def _js_esm(ws: Path, dry_run: bool) -> RecipeExecutionResult:
    res = RecipeExecutionResult(recipe_id="js-esm", recipe_name="CommonJS → ES Modules (ESM)")
    files = _iter_files(ws, suffixes={".js", ".jsx", ".mjs", ".cjs"})
    applied = 0
    for f in files:
        if "node_modules" in f.relative_to(ws).parts:
            continue
        orig = f.read_text(encoding="utf-8", errors="replace")
        new = _to_esm(orig)
        if new != orig:
            applied += 1
            rel = str(f.relative_to(ws))
            if not dry_run:
                f.write_text(new, encoding="utf-8")
            res.changed_files.append(_build_change(
                rel, orig, new, "esm-converter",
                "CJS_TO_ESM", "Converted CommonJS require/module.exports to ES import/export syntax."))
    if applied:
        res.notes.append(f"Converted {applied} file(s) from CommonJS to ESM syntax.")
    else:
        res.notes.append("No require()/module.exports patterns found.")
    if not files:
        res.status = "NOT_APPLICABLE"
    return res


# ── Handlers: Optional chaining ───────────────────────────────────────────────

# x && x.y   →  x?.y
_AND_CHAIN = re.compile(r"\b([A-Za-z_$][\w$]*)\s*&&\s*\1\.", )
# x != null && x.y  /  x !== null && x.y
_NULL_AND = re.compile(r"\b([A-Za-z_$][\w$]*)\s*(?:!==\s*null|!= null|!= undefined|!==\s*undefined)\s*&&\s*\1\.")
# x == null ? a : x.y  →  x?.y ?? a   (simplified: guarded member access)
_TARGET = re.compile(r"\b([A-Za-z_$][\w$]*)\s*[!=]==?\s*null\s*\?\s*(?:null|undefined)\s*:\s*\1\.")


def _add_optional_chaining(content: str) -> str:
    result = content
    result = _NULL_AND.sub(r"\1?.", result)
    result = _AND_CHAIN.sub(r"\1?.", result)
    result = _TARGET.sub(r"\1?.", result)
    return result


@register("js-optional-chaining")
def _js_optional_chaining(ws: Path, dry_run: bool) -> RecipeExecutionResult:
    res = RecipeExecutionResult(recipe_id="js-optional-chaining", recipe_name="Optional Chaining & Nullish Coalescing")
    files = _iter_files(ws, suffixes={".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"})
    applied = 0
    for f in files:
        orig = f.read_text(encoding="utf-8", errors="replace")
        new = _add_optional_chaining(orig)
        if new != orig:
            applied += 1
            rel = str(f.relative_to(ws))
            if not dry_run:
                f.write_text(new, encoding="utf-8")
            res.changed_files.append(_build_change(
                rel, orig, new, "optional-chaining-rewriter",
                "OPTIONAL_CHAINING", "Replaced verbose null/undefined guards with ?. optional chaining."))
    if applied:
        res.notes.append(f"Applied optional chaining to {applied} file(s).")
    else:
        res.notes.append("No candidate guard patterns found.")
    if not files:
        res.status = "NOT_APPLICABLE"
    return res


# ── Handlers: TypeScript strict mode ──────────────────────────────────────────

@register("ts-strict-mode")
def _ts_strict_mode(ws: Path, dry_run: bool) -> RecipeExecutionResult:
    res = RecipeExecutionResult(recipe_id="ts-strict-mode", recipe_name="TypeScript Strict Mode")
    candidates = list(ws.rglob("tsconfig.json")) + list(ws.rglob("tsconfig.base.json"))
    if not candidates:
        res.status = "NOT_APPLICABLE"
        res.notes.append("No tsconfig.json found.")
        return res

    for tsconfig in candidates:
        if is_ignored_path(tsconfig):
            continue
        rel = str(tsconfig.relative_to(ws))
        try:
            data = json.loads(tsconfig.read_text(encoding="utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError):
            res.errors.append(f"{rel}: could not parse tsconfig JSON")
            continue

        compiler = data.setdefault("compilerOptions", {})
        before = compiler.get("strict")
        if before is True:
            continue
        before_content = json.dumps(data, indent=2)
        compiler["strict"] = True
        new_content = json.dumps(data, indent=2) + "\n"
        res.notes.append(f"{rel}: enabled strict=true (was {before if before is not None else 'unset'}).")
        if not dry_run:
            tsconfig.write_text(new_content, encoding="utf-8")
        res.changed_files.append(_build_change(
            rel, before_content, new_content, "ts-strict",
            "TS_STRICT_MODE", "Enabled compilerOptions.strict in tsconfig."))
    if not res.changed_files and not res.errors:
        res.status = "NOT_APPLICABLE"
        res.notes.append("TypeScript strict mode was already enabled.")
    return res


# ── Handlers: Replace any ──────────────────────────────────────────────────────

_ANY_ANNOTATION = re.compile(r"\bany\b(?=\s*[,)}\]])")


def _replace_any(content: str) -> str:
    # Replace 'any' in annotation positions (: any, <any>, any[]) with 'unknown',
    # and `any[]` with `unknown[]`; leaves `any` usage in expressions untouched.
    result = re.sub(r"\bany\s*\[\s*\]", "unknown[]", content)
    result = re.sub(r"(:\s*)any\b", r"\1unknown", result)
    result = re.sub(r"<any>", "<unknown>", result)
    return result


@register("ts-no-any")
def _ts_no_any(ws: Path, dry_run: bool) -> RecipeExecutionResult:
    res = RecipeExecutionResult(recipe_id="ts-no-any", recipe_name="Replace 'any' with Specific Types")
    files = _iter_files(ws, suffixes={".ts", ".tsx"})
    applied = 0
    for f in files:
        orig = f.read_text(encoding="utf-8", errors="replace")
        new = _replace_any(orig)
        if new != orig:
            applied += 1
            rel = str(f.relative_to(ws))
            if not dry_run:
                f.write_text(new, encoding="utf-8")
            res.changed_files.append(_build_change(
                rel, orig, new, "any-replacer",
                "TS_NO_ANY", "Replaced unsafe 'any' annotations with 'unknown' (annotate real types next)."))
    if applied:
        res.notes.append(f"Replaced unsafe 'any' annotations in {applied} file(s) with 'unknown'.")
        res.notes.append("Manual pass recommended: replace 'unknown' with precise domain types.")
    else:
        res.notes.append("No 'any' annotations found (or already replaced).")
    if not files:
        res.status = "NOT_APPLICABLE"
    return res


# ── Handlers: Security ─────────────────────────────────────────────────────────

_SECRET_PATTERNS = [
    (re.compile(r"(AIza[0-9A-Za-z\-_]{35})"), "HIGH", "Google API key", "google_api_key"),
    (re.compile(r"(AKIA[0-9A-Z]{16})"), "HIGH", "AWS Access Key ID", "aws_access_key"),
    (re.compile(r"(sk-[0-9A-Za-z]{20,})"), "CRITICAL", "OpenAI API key", "openai_key"),
    (re.compile(r"(ghp_[0-9A-Za-z]{36})"), "CRITICAL", "GitHub Personal Access Token", "github_token"),
    (re.compile(r"(xox[bp]-[0-9A-Za-z-]{10,})"), "HIGH", "Slack token", "slack_token"),
    (re.compile(r"(-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----)"), "HIGH", "Private key block", "private_key"),
    (re.compile(r"(-----BEGIN CERTIFICATE-----)"), "LOW", "Certificate block", "certificate"),
    (re.compile(r"(password\s*[:=]\s*['\"][^'\"]{4,}['\"])", re.IGNORECASE), "MEDIUM", "Hardcoded password", "password"),
    (re.compile(r"(secret\s*[:=]\s*['\"][^'\"]{4,}['\"])", re.IGNORECASE), "MEDIUM", "Hardcoded secret", "secret"),
    (re.compile(r"(api[_-]?key\s*[:=]\s*['\"][^'\"]{8,}['\"])", re.IGNORECASE), "MEDIUM", "API key literal", "api_key"),
]


@register("sec-secrets-scan")
def _sec_secrets_scan(ws: Path, dry_run: bool) -> RecipeExecutionResult:
    res = RecipeExecutionResult(recipe_id="sec-secrets-scan", recipe_name="Secrets & Credential Detection")
    files = _iter_files(ws)
    # Skip lockfiles / large binaries / minified output
    for f in files:
        rel = str(f.relative_to(ws))
        if f.suffix.lower() in (".lock", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2", ".pdf"):
            continue
        if f.name.lower() in ("package-lock.json", "pnpm-lock.yaml", "yarn.lock"):
            continue
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pat, severity, label, _kind in _SECRET_PATTERNS:
            for m in pat.finditer(content):
                snippet = m.group(1)
                if len(snippet) > 48:
                    snippet = snippet[:48] + "..."
                res.findings.append(RecipeFinding(
                    file=rel,
                    severity=severity,
                    message=f"Possible {label} detected",
                    evidence=snippet,
                ))
                break  # one finding per file per pattern class

    if res.findings:
        res.notes.append(f"Found {len(res.findings)} potential secret(s) across the workspace.")
        res.notes.append("Review each finding; remove or rotate credentials before deploying.")
    else:
        res.notes.append("No high-confidence secrets detected.")
    if not files:
        res.status = "NOT_APPLICABLE"
    return res


# ── Handlers: CI pipeline ──────────────────────────────────────────────────────

_DEFAULT_CI_YML = """name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install dependencies
        run: npm ci || npm install
      - name: Lint
        run: npm run lint
      - name: Build
        run: npm run build
      - name: Test
        run: npm test
"""


@register("sec-dep-audit")
def _sec_dep_audit(ws: Path, dry_run: bool) -> RecipeExecutionResult:
    """Reuse the dependency-analysis pipeline to report outdated/vulnerable deps."""
    res = RecipeExecutionResult(recipe_id="sec-dep-audit", recipe_name="Dependency Security Audit")

    try:
        from app.dependency_analysis.service import DependencyAnalysisService
        service = DependencyAnalysisService()
        # plan_only=True so this recipe is advisory (no file mutation)
        analysis = service.analyze(str(ws), plan_only=True)
    except Exception as exc:
        res.success = False
        res.status = "FAILED"
        res.errors.append(f"Dependency scan failed: {exc}")
        return res

    outdated = getattr(analysis, "outdated", []) or []
    lookup_failed = getattr(analysis, "lookup_failed", []) or []
    constraint_blocked = getattr(analysis, "constraint_blocked", []) or []

    for name in outdated:
        res.findings.append(RecipeFinding(
            file=getattr(analysis, "workspace_path", str(ws)),
            severity="MEDIUM",
            message=f"Dependency '{name}' is outdated and may contain unpatched CVEs.",
            evidence=name,
        ))
    for name in lookup_failed:
        res.findings.append(RecipeFinding(
            file=getattr(analysis, "workspace_path", str(ws)),
            severity="LOW",
            message=f"Could not resolve latest version for '{name}'.",
            evidence=name,
        ))
    for name in constraint_blocked:
        res.findings.append(RecipeFinding(
            file=getattr(analysis, "workspace_path", str(ws)),
            severity="MEDIUM",
            message=f"Dependency '{name}' is blocked by a version constraint (audit manually).",
            evidence=name,
        ))

    if res.findings:
        res.notes.append(f"Found {len(res.findings)} dependency issue(s): {len(outdated)} outdated, "
                         f"{len(constraint_blocked)} constraint-blocked, {len(lookup_failed)} unresolved.")
        res.notes.append("Approve safe patch upgrades in the Dependency Review step, then re-run.")
    else:
        res.notes.append("All analyzed dependencies are up to date.")
    return res


# ── Handlers: CI pipeline ──────────────────────────────────────────────────────

@register("gen-ci-pipeline")
def _gen_ci_pipeline(ws: Path, dry_run: bool) -> RecipeExecutionResult:
    res = RecipeExecutionResult(recipe_id="gen-ci-pipeline", recipe_name="Generate CI/CD Pipeline")
    gh_dir = ws / ".github" / "workflows"
    existing = list(gh_dir.glob("*.yml")) + list(gh_dir.glob("*.yaml")) if gh_dir.exists() else []

    # Prefer language-appropriate template
    yml = _DEFAULT_CI_YML
    if any(f.suffix.lower() == ".py" for f in _iter_files(ws, suffixes={".py"})):
        yml = _DEFAULT_CI_YML.replace("npm ci || npm install", "pip install -r requirements.txt")
        yml = yml.replace("npm run lint", "ruff check .")
        yml = yml.replace("npm run build", "python -m compileall .")
        yml = yml.replace("npm test", "pytest")
    elif any(f.suffix.lower() in (".csproj", ".cs") for f in _iter_files(ws, suffixes={".csproj", ".cs"})):
        yml = _DEFAULT_CI_YML.replace("npm ci || npm install", "dotnet restore")
        yml = yml.replace("npm run lint", "dotnet format --verify-no-changes")
        yml = yml.replace("npm run build", "dotnet build --configuration Release")
        yml = yml.replace("npm test", "dotnet test")

    if existing:
        res.notes.append(f"CI pipeline already exists ({existing[0].name}); left unchanged.")
        res.status = "NOT_APPLICABLE"
        return res

    target_file = gh_dir / "ci.yml"
    rel = str(target_file.relative_to(ws))
    if not dry_run:
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(yml, encoding="utf-8")
    res.changed_files.append(FileChangeMetadata(
        file=rel,
        status="ADDED",
        after_content=yml,
        diff="+ Generated GitHub Actions workflow\n",
        tools=["ci-generator"],
        changes=[{"type": "CI_PIPELINE", "description": "Generated GitHub Actions CI workflow."}],
    ))
    res.notes.append(f"Generated GitHub Actions workflow at {rel}.")
    return res


# ── Handlers: Python ───────────────────────────────────────────────────────────

_FORMAT_CALLS = re.compile(
    r"(['\"])"                       # opening quote  (group 1)
    r"((?:(?!\1).)*)"                # template body  (group 2)
    r"\1\s*\.\s*format\s*\(([^)]*)\)",  # .format(args) (group 3)
    re.DOTALL,
)

# Split top-level format args on commas (ignoring nested quotes/brackets)
_ARG_SPLIT_RE = re.compile(r",\s*(?=(?:[^'\"]|'[^']*'|\"[^\"]*\")*$)")

# Bare '{}' slot in a format template
_BARE_SLOT_RE = re.compile(r"\{\s*}")


def _py_f_strings(content: str) -> str:
    """Convert '{0} {1}'.format(a, b) / '{}'.format(x) into f-strings.

    Conservative rules:
      - Only positional placeholders ({}, {0}, {1}, ...) are converted.
      - Args must be simple identifiers, attribute chains, or string/number literals.
      - Any template containing literal {{ or }} is left untouched.
      - Named-field templates ('.format(name=...)') are left untouched.
    """
    def _is_simple_expr(arg: str) -> bool:
        if arg in ("True", "False", "None"):
            return True
        if arg.startswith(("'", '"')) and arg.endswith((arg[0],)) and len(arg) >= 2:
            return False  # string literals can conflict with the f-string quote
        return bool(re.match(r"^[A-Za-z_]\w*([.\[]\w*|\['[^']*'\])*$", arg))

    def repl(m: re.Match) -> str:
        quote = m.group(1)
        template = m.group(2)
        args_raw = m.group(3) or ""
        if "{" not in template or "}}" in template or "{{" in template:
            return m.group(0)
        if "=" in args_raw:
            return m.group(0)  # named args — skip

        args = [a.strip() for a in _ARG_SPLIT_RE.split(args_raw)]
        args = [a for a in args if a]
        if not args or not all(_is_simple_expr(a) for a in args):
            return m.group(0)

        # Count unique placeholders
        try:
            placeholders = re.findall(r"\{(\d*)\}", template)
        except re.error:
            return m.group(0)
        if len(placeholders) != len(args):
            return m.group(0)

        # Validate numbered indices and figure out which args bare slots consume.
        numbered = []
        for ph in placeholders:
            if ph != "":
                try:
                    idx = int(ph)
                except ValueError:
                    return m.group(0)
                if idx >= len(args):
                    return m.group(0)
                numbered.append(idx)
        used_by_number = set(numbered)
        if len(numbered) != len(used_by_number):
            return m.group(0)  # duplicate numbered placeholder — not a simple format
        unused_args = [i for i in range(len(args)) if i not in used_by_number]
        bare_count = len(placeholders) - len(numbered)
        if len(unused_args) < bare_count:
            return m.group(0)

        new_body = template
        for i, arg in enumerate(args):
            new_body = new_body.replace(f"{{{i}}}", f"{{{arg}}}")
        # Replace bare '{}' slots in order of appearance with the next unused arg
        if bare_count:
            unused_iter = iter(unused_args)
            new_body = _BARE_SLOT_RE.sub(
                lambda _: f"{{{args[next(unused_iter)]}}}", new_body
            )
        if f"{{{args[0]}}}" not in new_body:
            return m.group(0)  # nothing safe to convert
        return "f" + quote + new_body + quote

    return _FORMAT_CALLS.sub(repl, content)


@register("py-f-strings")
def _py_f_strings_handler(ws: Path, dry_run: bool) -> RecipeExecutionResult:
    res = RecipeExecutionResult(recipe_id="py-f-strings", recipe_name="Modernize: f-strings")
    files = _iter_files(ws, suffixes={".py"})
    applied = 0
    for f in files:
        orig = f.read_text(encoding="utf-8", errors="replace")
        new = _py_f_strings(orig)
        if new != orig:
            applied += 1
            rel = str(f.relative_to(ws))
            if not dry_run:
                f.write_text(new, encoding="utf-8")
            res.changed_files.append(_build_change(
                rel, orig, new, "fstring-modernizer",
                "PY_F_STRINGS", "Converted .format() calls to f-strings."))
    if applied:
        res.notes.append(f"Converted {applied} file(s) to f-strings.")
    else:
        res.notes.append("No convertible .format() patterns found.")
    if not files:
        res.status = "NOT_APPLICABLE"
    return res


# ── Handlers: C# / .NET (Roslyn) ───────────────────────────────────────────────

def _csharp_adapter_and_plan(ws: Path, target_version: str = "net8.0"):
    """Instantiate the C# Roslyn adapter and build a target migration plan."""
    from app.adapters.base import CSharpRoslynAdapter
    from app.core.domain.models import TechnologyProfile
    adapter = CSharpRoslynAdapter()
    plan = adapter.create_plan(str(ws), TechnologyProfile(), target_version=target_version)
    return adapter, plan


def _csharp_recipe_result(rid: str, name: str, ws: Path, dry_run: bool, applied_changes: List, success: bool = True, notes: List[str] = None) -> RecipeExecutionResult:
    """Helper to return validation metrics and changed files for C# execution."""
    res = RecipeExecutionResult(recipe_id=rid, recipe_name=name)
    if notes:
        res.notes.extend(notes)
    
    if not applied_changes:
        res.status = "NOT_APPLICABLE"
        res.notes.append("No files require transformation.")
        return res

    res.changed_files.extend(applied_changes)
    
    if dry_run:
        res.status = "EXECUTED"
        res.notes.append(f"Dry run: {len(applied_changes)} file(s) would change.")
        return res

    from app.adapters.base import CSharpRoslynAdapter
    from app.core.domain.models import MigrationResult, MigrationStatistics
    adapter = CSharpRoslynAdapter()
    dummy_stats = MigrationStatistics(
        files_scanned=len(applied_changes),
        files_modified=len(applied_changes),
        files_unchanged=0,
        capabilities_run=1
    )
    dummy_res = MigrationResult(
        result_id="dummy", job_id="dummy", project_id="dummy", plan_id="dummy",
        status="SUCCESS", statistics=dummy_stats, changed_files=applied_changes
    )
    validation = adapter.validate(str(ws), dummy_res)
    res.notes.extend(validation.warnings)
    res.notes.append(
        f"Validation: build_passed={validation.build_passed}, "
        f"tests_passed={validation.tests_passed} ({validation.tests_total} test(s)), "
        f"warnings={len(validation.warnings)}."
    )
    if not validation.build_passed:
        res.status = "FAILED"
        res.success = False
        res.errors.extend(validation.errors)
    else:
        res.status = "EXECUTED"
        res.success = True
    return res


@register("cs-net6-upgrade")
def _cs_net6_upgrade(ws: Path, dry_run: bool) -> RecipeExecutionResult:
    """Invoke the CSharpRoslynAdapter to migrate .NET Framework projects to .NET 6/8.

    Apply mode runs the adapter's real transformation (file-scoped namespaces +
    <TargetFramework> upgrade) and reports build/validation results from the
    adapter's post-migration validation — never fabricating success.
    """
    res = RecipeExecutionResult(
        recipe_id="cs-net6-upgrade",
        recipe_name=".NET Framework → .NET 6/8 Upgrade",
    )
    from app.adapters.base import CSharpRoslynSyntaxTransformer
    adapter, plan = _csharp_adapter_and_plan(ws)
    target_version = plan.targets[0].target_version if plan.targets else "net8.0"

    if dry_run:
        preview = adapter.dry_run(str(ws), plan)
        if preview.notes:
            res.notes.append(preview.notes)
        transformer = CSharpRoslynSyntaxTransformer()
        applied = 0
        for f in _iter_files(ws, suffixes={".cs", ".csproj"}):
            orig = f.read_text(encoding="utf-8", errors="replace")
            if f.suffix.lower() == ".csproj":
                new = transformer.transform_csproj(orig, target_version)
                desc = "Preview: TargetFramework upgrade (dry run)."
            else:
                new = transformer.transform_code(orig, target_version)
                desc = "Preview: file-scoped namespace conversion (dry run)."
            if new != orig:
                applied += 1
                res.changed_files.append(_build_change(
                    str(f.relative_to(ws)), orig, new, "roslyn-net6-upgrade",
                    "CS_NET6_UPGRADE", desc))
        if applied:
            res.notes.append(f"Dry run: {applied} file(s) would change.")
        else:
            res.status = "NOT_APPLICABLE"
            res.notes.append("No C# files require transformation (already file-scoped / net8.0).")
        return res

    result = adapter.migrate(str(ws), plan)
    for fm in result.changed_files:
        res.changed_files.append(fm)

    if not res.changed_files:
        res.status = "NOT_APPLICABLE"
        res.notes.append("No C# files required transformation (already file-scoped / net8.0).")
        return res

    validation = adapter.validate(str(ws), result)
    res.notes.extend(validation.warnings)
    res.notes.append(
        f"Validation: build_passed={validation.build_passed}, "
        f"tests_passed={validation.tests_passed} ({validation.tests_total} test(s)), "
        f"warnings={len(validation.warnings)}."
    )
    if not validation.build_passed:
        res.status = "FAILED"
        res.success = False
        res.errors.extend(validation.errors)
    return res


@register("cs-net8-upgrade")
def _cs_net8_upgrade(ws: Path, dry_run: bool) -> RecipeExecutionResult:
    """Upgrade .csproj TargetFramework properties to net8.0."""
    from app.adapters.base import CSharpRoslynSyntaxTransformer
    transformer = CSharpRoslynSyntaxTransformer()
    applied = []
    
    for f in _iter_files(ws, suffixes={".csproj"}):
        orig = f.read_text(encoding="utf-8", errors="replace")
        new = transformer.transform_csproj(orig, "net8.0")
        if new != orig:
            if not dry_run:
                f.write_text(new, encoding="utf-8")
            applied.append(_build_change(
                str(f.relative_to(ws)), orig, new, "roslyn-net8-upgrade",
                "CS_NET8_UPGRADE", "Upgraded TargetFramework to net8.0"
            ))

    return _csharp_recipe_result("cs-net8-upgrade", ".NET Framework → .NET 8 Upgrade", ws, dry_run, applied)


@register("cs-nullable-ref")
def _cs_nullable_ref(ws: Path, dry_run: bool) -> RecipeExecutionResult:
    """Enable <Nullable>enable</Nullable> in .csproj files."""
    applied = []
    for f in _iter_files(ws, suffixes={".csproj"}):
        orig = f.read_text(encoding="utf-8", errors="replace")
        if "<Nullable>" in orig:
            continue
        match = re.search(r"<PropertyGroup\s*[^>]*>", orig, re.IGNORECASE)
        if match:
            pos = match.end()
            new = orig[:pos] + "\n    <Nullable>enable</Nullable>" + orig[pos:]
            if not dry_run:
                f.write_text(new, encoding="utf-8")
            applied.append(_build_change(
                str(f.relative_to(ws)), orig, new, "roslyn-nullable",
                "CS_NULLABLE_REF", "Enabled Nullable Reference Types"
            ))

    return _csharp_recipe_result("cs-nullable-ref", "Enable Nullable Reference Types", ws, dry_run, applied)


@register("cs-package-reference")
def _cs_package_reference(ws: Path, dry_run: bool) -> RecipeExecutionResult:
    """Migrate legacy reference HintPaths and packages.config to PackageReference."""
    import xml.etree.ElementTree as ET
    applied = []
    
    packages = []
    packages_config_files = list(ws.rglob("packages.config"))
    for pc_file in packages_config_files:
        if is_ignored_path(pc_file):
            continue
        try:
            xml_text = pc_file.read_text(encoding="utf-8", errors="replace")
            pc_root = ET.fromstring(xml_text)
            for pkg in pc_root.iter():
                pkg_tag = pkg.tag.split("}")[-1].lower()
                if pkg_tag == "package":
                    pid = pkg.get("id")
                    ver = pkg.get("version")
                    if pid and ver:
                        packages.append((pid, ver))
        except Exception:
            pass

    original_contents = {}
    for f in _iter_files(ws, suffixes={".csproj"}):
        orig = f.read_text(encoding="utf-8", errors="replace")
        try:
            root = ET.fromstring(orig)
            changed = False
            
            references_to_remove = []
            for item_group in root.findall(".//ItemGroup"):
                for ref in list(item_group):
                    ref_tag = ref.tag.split("}")[-1].lower()
                    if ref_tag == "reference":
                        hint_path = ref.find(".//HintPath")
                        if hint_path is not None and hint_path.text and "packages/" in hint_path.text.lower():
                            include_attr = ref.get("Include", "")
                            lib_name = include_attr.split(",")[0].strip()
                            references_to_remove.append((item_group, ref, lib_name))

            package_references_to_add = {}
            for item_group, ref, lib_name in references_to_remove:
                item_group.remove(ref)
                changed = True
                ver = "1.0.0"
                for pid, pver in packages:
                    if pid.lower() == lib_name.lower():
                        ver = pver
                        break
                package_references_to_add[lib_name] = ver

            for pid, pver in packages:
                if pid not in package_references_to_add:
                    package_references_to_add[pid] = pver
                    changed = True

            if package_references_to_add:
                item_group = ET.SubElement(root, "ItemGroup")
                for pid, pver in package_references_to_add.items():
                    pref = ET.SubElement(item_group, "PackageReference")
                    pref.set("Include", pid)
                    pref.set("Version", pver)
                changed = True

            if changed:
                new = ET.tostring(root, encoding="utf-8").decode("utf-8")
                original_contents[f] = orig
                if not dry_run:
                    f.write_text(new, encoding="utf-8")
                applied.append(_build_change(
                    str(f.relative_to(ws)), orig, new, "roslyn-package-reference",
                    "CS_PACKAGE_REFERENCE", "Migrated legacy Reference HintPaths to PackageReference"
                ))
        except Exception:
            pass

    if not applied:
        return _csharp_recipe_result("cs-package-reference", "Migrate to PackageReference", ws, dry_run, applied)

    if dry_run:
        return _csharp_recipe_result("cs-package-reference", "Migrate to PackageReference", ws, dry_run, applied)

    from app.adapters.base import CSharpRoslynAdapter
    from app.core.domain.models import MigrationResult, MigrationStatistics
    adapter = CSharpRoslynAdapter()
    dummy_stats = MigrationStatistics(
        files_scanned=len(applied),
        files_modified=len(applied),
        files_unchanged=0,
        capabilities_run=1
    )
    dummy_res = MigrationResult(
        result_id="dummy", job_id="dummy", project_id="dummy", plan_id="dummy",
        status="SUCCESS", statistics=dummy_stats, changed_files=applied
    )
    validation = adapter.validate(str(ws), dummy_res)

    if not validation.build_passed:
        # Undo changes to csproj
        for f, orig_content in original_contents.items():
            f.write_text(orig_content, encoding="utf-8")
        res = RecipeExecutionResult(recipe_id="cs-package-reference", recipe_name="Migrate to PackageReference")
        res.status = "FAILED"
        res.success = False
        res.notes.extend(validation.warnings)
        res.notes.append("Validation failed. Restored original project files.")
        res.errors.extend(validation.errors)
        return res

    for pc_file in packages_config_files:
        if not is_ignored_path(pc_file):
            try:
                pc_file.unlink()
                applied.append(FileChangeMetadata(
                    file=str(pc_file.relative_to(ws)),
                    status="DELETED",
                    tools=["Roslyn"],
                    before_content="<packages />",
                    after_content="",
                    diff="--- packages.config\n+++ /dev/null\n",
                    changes=[{"type": "PACKAGES_CONFIG_DELETION", "description": "Deleted packages.config file"}]
                ))
            except Exception:
                pass

    res = RecipeExecutionResult(recipe_id="cs-package-reference", recipe_name="Migrate to PackageReference")
    res.changed_files.extend(applied)
    res.status = "EXECUTED"
    res.success = True
    res.notes.extend(validation.warnings)
    res.notes.append(
        f"Validation: build_passed={validation.build_passed}, "
        f"tests_passed={validation.tests_passed} ({validation.tests_total} test(s)), "
        f"warnings={len(validation.warnings)}."
    )
    return res


@register("cs-file-scoped-namespace")
def _cs_file_scoped_namespace(ws: Path, dry_run: bool) -> RecipeExecutionResult:
    """Convert C# namespace declarations to file-scoped syntax."""
    from app.adapters.base import CSharpRoslynSyntaxTransformer
    transformer = CSharpRoslynSyntaxTransformer()
    applied = []
    
    for f in _iter_files(ws, suffixes={".cs"}):
        orig = f.read_text(encoding="utf-8", errors="replace")
        new = transformer.transform_code(orig, "net8.0")
        if new != orig:
            if not dry_run:
                f.write_text(new, encoding="utf-8")
            applied.append(_build_change(
                str(f.relative_to(ws)), orig, new, "roslyn-file-scoped-ns",
                "CS_FILE_SCOPED_NAMESPACE", "Converted namespace block to file-scoped namespace (C# 10+)"
            ))

    return _csharp_recipe_result("cs-file-scoped-namespace", "File-scoped Namespace Conversion", ws, dry_run, applied)


@register("cs-var-modernization")
def _cs_var_modernization(ws: Path, dry_run: bool) -> RecipeExecutionResult:
    """Replace explicit variable declarations with var."""
    applied = []
    pattern = r"\b([a-zA-Z0-9_.]+)\s+([a-zA-Z0-9_]+)\s*=\s*new\s+\1\s*\((.*?)\)\s*;"
    keywords_and_builtins = {
        "int", "string", "double", "float", "bool", "char", "long", "short", "byte", "decimal",
        "return", "throw", "yield", "class", "namespace", "using", "public", "private", 
        "protected", "internal", "static", "readonly", "override", "virtual", "new", "true", "false"
    }
    
    for f in _iter_files(ws, suffixes={".cs"}):
        orig = f.read_text(encoding="utf-8", errors="replace")
        
        def repl(match):
            type_name, var_name, args = match.groups()
            if type_name in keywords_and_builtins or var_name in keywords_and_builtins:
                return match.group(0)
            return f"var {var_name} = new {type_name}({args});"

        new, count = re.subn(pattern, repl, orig)
        if count > 0:
            if not dry_run:
                f.write_text(new, encoding="utf-8")
            applied.append(_build_change(
                str(f.relative_to(ws)), orig, new, "roslyn-var-modernization",
                "CS_VAR_MODERNIZATION", "Replaced redundant explicit type with var"
            ))

    return _csharp_recipe_result("cs-var-modernization", "Local Variable var Modernization", ws, dry_run, applied)


def get_executor_help() -> list[str]:
    return sorted(_REGISTRY.keys())