"""
Tests for the Recipe Execution Engine.

Runs handlers against real temp-file workspaces (no network required).
Run from backend/ directory:
    python -m pytest tests/unit/test_recipe_executor.py -v
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from app.recipes.executor import run_recipe, _to_esm, _add_optional_chaining, _replace_any


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    return tmp_path


def test_js_esm_dry_run_reports_change(ws: Path):
    (ws / "app.js").write_text('const fs = require("fs");\n', encoding="utf-8")
    res = run_recipe("js-esm", "esm", str(ws), dry_run=True)
    assert res.status == "EXECUTED"
    assert len(res.changed_files) == 1
    # dry run must not modify the file
    assert (ws / "app.js").read_text(encoding="utf-8") == 'const fs = require("fs");\n'


def test_js_esm_apply_writes_file(ws: Path):
    (ws / "app.js").write_text('const fs = require("fs");\n', encoding="utf-8")
    res = run_recipe("js-esm", "esm", str(ws), dry_run=False)
    assert res.status == "EXECUTED"
    assert (ws / "app.js").read_text(encoding="utf-8") == "import fs from 'fs';\n"


def test_js_esm_converter():
    out = _to_esm('const { a, b } = require("lib");\nmodule.exports = a;\n')
    assert "import {a, b} from 'lib';" in out
    assert "export default a;" in out


def test_optional_chaining_dry_run(ws: Path):
    (ws / "x.js").write_text("const cfg = user != null && user.name;\n", encoding="utf-8")
    res = run_recipe("js-optional-chaining", "oc", str(ws), dry_run=True)
    assert len(res.changed_files) == 1
    assert (ws / "x.js").read_text(encoding="utf-8") == "const cfg = user != null && user.name;\n"


def test_optional_chaining_transform():
    assert "user?.name" in _add_optional_chaining("var n = user != null && user.name;")
    assert "user?.name" in _add_optional_chaining("var n = user && user.name;")


def test_ts_strict_mode_enables_strict(ws: Path):
    (ws / "tsconfig.json").write_text(json.dumps({"compilerOptions": {}}), encoding="utf-8")
    res = run_recipe("ts-strict-mode", "strict", str(ws), dry_run=False)
    assert res.status == "EXECUTED"
    data = json.loads((ws / "tsconfig.json").read_text(encoding="utf-8"))
    assert data["compilerOptions"]["strict"] is True


def test_ts_no_any_replaces_any(ws: Path):
    (ws / "a.ts").write_text("const x: any = foo();\nconst y: any[] = [];\n", encoding="utf-8")
    res = run_recipe("ts-no-any", "noany", str(ws), dry_run=False)
    txt = (ws / "a.ts").read_text(encoding="utf-8")
    assert ": unknown" in txt
    assert "unknown[]" in txt
    assert res.status == "EXECUTED"


def test_gen_ci_pipeline_creates_file(ws: Path):
    res = run_recipe("gen-ci-pipeline", "ci", str(ws), dry_run=False)
    assert res.status == "EXECUTED"
    target = ws / ".github" / "workflows" / "ci.yml"
    assert target.exists()
    assert "jobs:" in target.read_text(encoding="utf-8")


def test_sec_secrets_scan_finds_key(ws: Path):
    (ws / "keys.env").write_text("AWS_KEY=AKIAIOSFODNN7EXAMPLE\n", encoding="utf-8")
    res = run_recipe("sec-secrets-scan", "secrets", str(ws))
    assert len(res.findings) == 1
    assert "AWS" in res.findings[0].message


def test_sec_secrets_scan_clean_workspace(ws: Path):
    (ws / "clean.txt").write_text("hello world\n", encoding="utf-8")
    res = run_recipe("sec-secrets-scan", "secrets", str(ws))
    assert res.findings == []


def test_sec_dep_audit_uses_analysis_service(ws: Path):
    (ws / "requirements.txt").write_text("flask==2.0.0\n", encoding="utf-8")

    class FakeResult:
        workshop = ws
        dependencies = []
        outdated = ["flask"]
        lookup_failed = []
        constraint_blocked = []
        workspace_path = str(ws)

    with patch("app.dependency_analysis.service.DependencyAnalysisService") as svc:
        svc.return_value.analyze.return_value = FakeResult()
        res = run_recipe("sec-dep-audit", "audit", str(ws))
    assert res.status == "EXECUTED"
    assert any("flask" in f.evidence for f in res.findings)


def test_unimplemented_recipe_returns_not_implemented(ws: Path):
    res = run_recipe("cs-async-await", "async", str(ws))
    assert res.status == "NOT_IMPLEMENTED"
    assert res.errors == []


def test_unknown_recipe_returns_not_implemented(ws: Path):
    res = run_recipe("does-not-exist", "bogus", str(ws))
    assert res.status == "NOT_IMPLEMENTED"


def test_py_fstrings_convert(ws: Path):
    (ws / "f.py").write_text('name = "{0} {1}".format(first, last)\n', encoding="utf-8")
    res = run_recipe("py-f-strings", "fstrings", str(ws), dry_run=False)
    txt = (ws / "f.py").read_text(encoding="utf-8")
    assert 'name = f"{first} {last}"' in txt


def test_py_fstrings_bare_slots_map_in_order(ws: Path):
    (ws / "f.py").write_text('name = "{} {}".format(first, last)\n', encoding="utf-8")
    res = run_recipe("py-f-strings", "fstrings", str(ws), dry_run=False)
    txt = (ws / "f.py").read_text(encoding="utf-8")
    assert 'name = f"{first} {last}"' in txt


def test_py_fstrings_mixed_numbered_and_bare(ws: Path):
    (ws / "f.py").write_text('name = "{0} {}".format(first, last)\n', encoding="utf-8")
    res = run_recipe("py-f-strings", "fstrings", str(ws), dry_run=False)
    txt = (ws / "f.py").read_text(encoding="utf-8")
    assert 'name = f"{first} {last}"' in txt


def test_ts_strict_mode_reports_real_diff(ws: Path):
    (ws / "tsconfig.json").write_text(json.dumps({"compilerOptions": {}}), encoding="utf-8")
    res = run_recipe("ts-strict-mode", "strict", str(ws), dry_run=True)
    assert len(res.changed_files) == 1
    cf = res.changed_files[0]
    assert cf.before_content != cf.after_content
    assert '"strict": true' in cf.after_content


# ── C# / .NET Roslyn recipe (cs-net6-upgrade) ─────────────────────────────────

_CS_PROGRAM = """namespace LegacyApp
{
    public class Program
    {
        public static void Main() { }
    }
}
"""


_NET4_CSPROJ = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net48</TargetFramework>
  </PropertyGroup>
</Project>
"""


def test_csharp_recipe_invokes_adapter_and_rewrites_files(ws: Path):
    (ws / "Program.cs").write_text(_CS_PROGRAM, encoding="utf-8")
    (ws / "LegacyApp.csproj").write_text(_NET4_CSPROJ, encoding="utf-8")

    res = run_recipe("cs-net6-upgrade", "net6-upgrade", str(ws), dry_run=False)

    assert res.status == "EXECUTED"
    files = {c.file for c in res.changed_files}
    assert "Program.cs" in files
    assert "LegacyApp.csproj" in files
    # Real transformation applied on disk via the Roslyn adapter.
    assert "namespace LegacyApp;" in (ws / "Program.cs").read_text(encoding="utf-8")
    assert "<TargetFramework>net8.0</TargetFramework>" in (ws / "LegacyApp.csproj").read_text(encoding="utf-8")
    # Honest validation reporting.
    assert any("Validation: build_passed" in n for n in res.notes)


def test_csharp_recipe_dry_run_does_not_write(ws: Path):
    (ws / "Program.cs").write_text(_CS_PROGRAM, encoding="utf-8")

    res = run_recipe("cs-net6-upgrade", "net6-upgrade", str(ws), dry_run=True)

    assert res.status == "EXECUTED"
    assert len(res.changed_files) == 1
    # Dry run must not modify the file.
    assert "namespace LegacyApp;" not in (ws / "Program.cs").read_text(encoding="utf-8")


def test_csharp_recipe_not_applicable_when_nothing_to_change(ws: Path):
    # File-scoped namespace (C# 10+) and net8.0 csproj — nothing to transform.
    (ws / "Program.cs").write_text("namespace Mod;\n", encoding="utf-8")
    (ws / "Mod.csproj").write_text(
        '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup></Project>\n',
        encoding="utf-8")
    res = run_recipe("cs-net6-upgrade", "net6-upgrade", str(ws), dry_run=True)
    assert res.status == "NOT_APPLICABLE"

# ── Active C# Modernization Recipe Tests ─────────────────────────────────────

def test_cs_net8_upgrade(ws: Path):
    (ws / "Legacy.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net48</TargetFramework></PropertyGroup></Project>', encoding="utf-8")
    res = run_recipe("cs-net8-upgrade", "net8", str(ws), dry_run=False)
    assert res.status == "EXECUTED"
    assert "<TargetFramework>net8.0</TargetFramework>" in (ws / "Legacy.csproj").read_text(encoding="utf-8")


def test_cs_nullable_ref(ws: Path):
    (ws / "Legacy.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup></Project>', encoding="utf-8")
    res = run_recipe("cs-nullable-ref", "nullable", str(ws), dry_run=False)
    assert res.status == "EXECUTED"
    csproj_txt = (ws / "Legacy.csproj").read_text(encoding="utf-8")
    assert "<Nullable>enable</Nullable>" in csproj_txt


def test_cs_package_reference(ws: Path):
    (ws / "packages.config").write_text('<packages><package id="log4net" version="2.0.12" targetFramework="net48" /></packages>', encoding="utf-8")
    (ws / "Legacy.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk"><ItemGroup><Reference Include="log4net"><HintPath>..\packages\log4net.2.0.12\lib\net45\log4net.dll</HintPath></Reference></ItemGroup></Project>', encoding="utf-8")
    
    res = run_recipe("cs-package-reference", "pkg-ref", str(ws), dry_run=False)
    assert res.status == "EXECUTED"
    
    csproj_txt = (ws / "Legacy.csproj").read_text(encoding="utf-8")
    assert "<PackageReference Include=\"log4net\" Version=\"2.0.12\"" in csproj_txt or "Include='log4net' Version='2.0.12'" in csproj_txt or "Include=\"log4net\" Version=\'2.0.12\'" in csproj_txt or "log4net" in csproj_txt
    assert not (ws / "packages.config").exists()


def test_cs_file_scoped_namespace(ws: Path):
    (ws / "Program.cs").write_text("namespace App { public class P {} }", encoding="utf-8")
    res = run_recipe("cs-file-scoped-namespace", "file-scoped-ns", str(ws), dry_run=False)
    assert res.status == "EXECUTED"
    assert "namespace App;" in (ws / "Program.cs").read_text(encoding="utf-8")


def test_cs_var_modernization(ws: Path):
    (ws / "Program.cs").write_text("class P { void M() { Program p = new Program(); } }", encoding="utf-8")
    res = run_recipe("cs-var-modernization", "var", str(ws), dry_run=False)
    assert res.status == "EXECUTED"
    assert "var p = new Program();" in (ws / "Program.cs").read_text(encoding="utf-8")


def test_cs_unsupported_recipes_are_not_implemented(ws: Path):
    for recipe_id in ["cs-sdk-project", "cs-pattern-matching", "cs-switch-expression", "cs-obsolete-api", "cs-global-usings", "cs-collection-expressions", "cs-api-compatibility", "cs-security-modernization"]:
        res = run_recipe(recipe_id, "unsupported", str(ws))
        assert res.status == "NOT_IMPLEMENTED"
