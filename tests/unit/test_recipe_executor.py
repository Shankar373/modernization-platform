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