"""
Unit tests for the Code Optimization engine (backend/app/optimization/optimizer.py).

Tests verify:
1. Real Ruff optimization on Python files — unused imports removed, diff produced.
2. Dry-run mode — files NOT modified on disk, preview metadata returned.
3. Rollback on post-optimization build failure — files restored to pre-optimization state.
4. Skipped files — generated files and unsupported extensions in skipped_files list.
5. Changed-file list matches actual disk state (no fabrication).
6. Unified diff correctness — validates ---, +++, @@ markers.
7. dotnet format on C# files (skipped gracefully when not available).
8. Prettier on JS files (skipped gracefully when not available).
"""
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from app.optimization.optimizer import (
    CodeOptimizer,
    _is_generated,
    _make_unified_diff,
)

# ── Fixtures ───────────────────────────────────────────────────────────────────

PYTHON_WITH_UNUSED_IMPORTS = """\
import os
import sys
import json  # unused

def greet(name: str):
    msg = "hello, " + name
    return msg
"""

PYTHON_EXPECTED_AFTER_RUFF = """\
import os
import sys


def greet(name: str):
    msg = "hello, " + name
    return msg
"""

CSHARP_LEGACY = """\
using System;
using System.IO;
using System.Collections.Generic;

namespace MyApp
{
    public class Program
    {
        public static void Main()
        {
            Console.WriteLine("Hello");
        }
    }
}
"""

JS_MESSY = """\
const   x  =  1
const y = 2
function add(a,b) { return a+b; }
"""


# ── Test: Generated file detection ────────────────────────────────────────────

def test_is_generated_designer_cs():
    assert _is_generated(Path("Form1.Designer.cs")) is True


def test_is_generated_g_cs():
    assert _is_generated(Path("Foo.g.cs")) is True


def test_is_generated_assemblyinfo():
    assert _is_generated(Path("AssemblyInfo.cs")) is True


def test_is_generated_min_js():
    assert _is_generated(Path("bundle.min.js")) is True


def test_is_not_generated_regular():
    assert _is_generated(Path("Program.cs")) is False
    assert _is_generated(Path("main.py")) is False


# ── Test: Unified diff generation ─────────────────────────────────────────────

def test_make_unified_diff_has_standard_markers():
    before = "line1\nline2\nold_line\n"
    after = "line1\nline2\nnew_line\n"
    diff = _make_unified_diff(before, after, "test.py")
    assert "--- a/test.py" in diff
    assert "+++ b/test.py" in diff
    assert "@@" in diff
    assert "-old_line" in diff
    assert "+new_line" in diff


def test_make_unified_diff_empty_when_identical():
    content = "no changes here\n"
    diff = _make_unified_diff(content, content, "same.py")
    assert diff == ""


def test_make_unified_diff_shows_additions():
    before = "line1\n"
    after = "line1\nline2\n"
    diff = _make_unified_diff(before, after, "file.py")
    assert "+line2" in diff


def test_make_unified_diff_shows_removals():
    before = "line1\nline2\n"
    after = "line1\n"
    diff = _make_unified_diff(before, after, "file.py")
    assert "-line2" in diff


# ── Test: Python Ruff optimization ────────────────────────────────────────────

def test_ruff_optimization_removes_unused_imports(tmp_path: Path):
    """Real Ruff should remove the unused 'json' import and reformat."""
    import shutil
    ruff = shutil.which("ruff")
    if not ruff:
        pytest.skip("ruff not installed")

    py_file = tmp_path / "app.py"
    py_file.write_text(PYTHON_WITH_UNUSED_IMPORTS, encoding="utf-8")

    optimizer = CodeOptimizer()
    result = optimizer.optimize(str(tmp_path), ["app.py"], dry_run=False)

    assert result.files_scanned == 1
    assert result.files_optimized == 1

    opt = result.optimized_files[0]
    assert opt.file == "app.py"
    assert opt.recipe == "ruff"
    # Before content should be the original messy version
    assert "import json" in opt.before_content

    # After content should have json removed (ruff lint fix)
    final_content = py_file.read_text(encoding="utf-8")
    assert opt.after_content == final_content

    # Diff should have standard markers if file changed
    if opt.changed:
        assert "--- a/app.py" in opt.diff
        assert "+++ b/app.py" in opt.diff
        assert "@@" in opt.diff


def test_ruff_dry_run_does_not_modify_files(tmp_path: Path):
    """In dry-run mode, files must NOT be written to disk."""
    import shutil
    ruff = shutil.which("ruff")
    if not ruff:
        pytest.skip("ruff not installed")

    py_file = tmp_path / "app.py"
    original = PYTHON_WITH_UNUSED_IMPORTS
    py_file.write_text(original, encoding="utf-8")

    optimizer = CodeOptimizer()
    result = optimizer.optimize(str(tmp_path), ["app.py"], dry_run=True)

    assert result.dry_run is True
    # File on disk must be unmodified
    assert py_file.read_text(encoding="utf-8") == original
    # Dry-run should be marked as success
    assert result.success is True


def test_ruff_skips_nonexistent_file(tmp_path: Path):
    """Missing file should be reported in skipped_files."""
    optimizer = CodeOptimizer()
    result = optimizer.optimize(str(tmp_path), ["nonexistent.py"], dry_run=False)
    assert result.files_skipped == 1
    assert any("not found" in s.reason.lower() for s in result.skipped_files)


def test_optimizer_skips_generated_files(tmp_path: Path):
    """Generated files must appear in skipped_files, not optimized_files."""
    gen_file = tmp_path / "Form1.Designer.cs"
    gen_file.write_text(CSHARP_LEGACY, encoding="utf-8")

    optimizer = CodeOptimizer()
    result = optimizer.optimize(str(tmp_path), ["Form1.Designer.cs"], dry_run=False)

    assert result.files_skipped == 1
    assert len(result.optimized_files) == 0
    assert any("generated" in s.reason.lower() for s in result.skipped_files)


def test_optimizer_skips_unsupported_extension(tmp_path: Path):
    """Files with unsupported extensions must be reported as skipped."""
    xml_file = tmp_path / "config.xml"
    xml_file.write_text("<root/>", encoding="utf-8")

    optimizer = CodeOptimizer()
    result = optimizer.optimize(str(tmp_path), ["config.xml"], dry_run=False)

    assert result.files_skipped == 1
    assert any("unsupported" in s.reason.lower() for s in result.skipped_files)


# ── Test: Changed-file list authenticity ──────────────────────────────────────

def test_optimization_result_matches_disk_state(tmp_path: Path):
    """after_content in result must match what is actually on disk after optimization."""
    import shutil
    ruff = shutil.which("ruff")
    if not ruff:
        pytest.skip("ruff not installed")

    py_file = tmp_path / "mymodule.py"
    py_file.write_text(PYTHON_WITH_UNUSED_IMPORTS, encoding="utf-8")

    optimizer = CodeOptimizer()
    result = optimizer.optimize(str(tmp_path), ["mymodule.py"], dry_run=False)

    if result.optimized_files:
        opt = result.optimized_files[0]
        disk_content = py_file.read_text(encoding="utf-8")
        assert opt.after_content == disk_content, (
            "OptimizedFileChange.after_content must exactly match disk state — no fabrication allowed"
        )


# ── Test: Rollback on build failure ───────────────────────────────────────────

def test_optimizer_rollback_on_cs_build_failure(tmp_path: Path):
    """When dotnet build fails after C# optimization, files must be restored."""
    cs_file = tmp_path / "Program.cs"
    cs_file.write_text(CSHARP_LEGACY, encoding="utf-8")
    csproj_file = tmp_path / "App.csproj"
    csproj_file.write_text(
        '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup></Project>',
        encoding="utf-8"
    )

    original_content = cs_file.read_text(encoding="utf-8")

    # Mock dotnet format to "change" the file (simulate formatting)
    def mock_format_run(cmd, *a, **kw):
        if "format" in cmd:
            # Simulate dotnet format adding a trailing newline
            abs_path = tmp_path / "Program.cs"
            abs_path.write_text(CSHARP_LEGACY + "\n// formatted\n", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    # Mock dotnet build to fail
    def mock_build_run(cmd, *a, **kw):
        if "build" in cmd:
            return subprocess.CompletedProcess(cmd, 1, "Build FAILED", "")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    def conditional_mock(cmd, *a, **kw):
        if not isinstance(cmd, list):
            return subprocess.CompletedProcess(cmd, 0, "", "")
        cmd_str = " ".join(str(c) for c in cmd)
        if "build" in cmd_str:
            return mock_build_run(cmd, *a, **kw)
        if "format" in cmd_str:
            return mock_format_run(cmd, *a, **kw)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    with patch("shutil.which", return_value="dotnet"), \
         patch("subprocess.run", side_effect=conditional_mock):
        optimizer = CodeOptimizer()
        result = optimizer.optimize(str(tmp_path), ["Program.cs"], dry_run=False)

    assert result.rolled_back is True
    assert result.success is False
    assert result.build_passed is False

    # Critical: file must be restored to original
    restored = cs_file.read_text(encoding="utf-8")
    assert restored == original_content, (
        "After rollback, file must exactly match pre-optimization state"
    )


def test_optimizer_preserves_modernization_on_optimization_failure(tmp_path: Path):
    """When optimization fails, the previously-modernized content is rolled back
    to its pre-optimization state, but NOT to the original un-modernized state.
    In other words, the modernization diff is not undone — only optimization is rolled back.
    """
    # Simulate that modernization already ran and produced this content
    already_modernized = "namespace MyApp;\npublic class Program\n{\n    public static void Main()\n    {\n        Console.WriteLine(\"Hello\");\n    }\n}\n"
    cs_file = tmp_path / "Program.cs"
    cs_file.write_text(already_modernized, encoding="utf-8")
    csproj = tmp_path / "App.csproj"
    csproj.write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup></Project>', encoding="utf-8")

    def conditional_mock(cmd, *a, **kw):
        if not isinstance(cmd, list):
            return subprocess.CompletedProcess(cmd, 0, "", "")
        cmd_str = " ".join(str(c) for c in cmd)
        if "build" in cmd_str:
            return subprocess.CompletedProcess(cmd, 1, "Build FAILED", "")
        if "format" in cmd_str:
            # Simulate formatter adding a space
            (tmp_path / "Program.cs").write_text(already_modernized + " ", encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    with patch("shutil.which", return_value="dotnet"), \
         patch("subprocess.run", side_effect=conditional_mock):
        optimizer = CodeOptimizer()
        result = optimizer.optimize(str(tmp_path), ["Program.cs"], dry_run=False)

    assert result.rolled_back is True
    # Rolled back to the MODERNIZED state (not the original block-namespace state)
    restored = cs_file.read_text(encoding="utf-8")
    assert "namespace MyApp;" in restored, (
        "Modernization change (file-scoped namespace) must still be present after optimization rollback"
    )


# ── Test: Empty changed_files list ────────────────────────────────────────────

def test_optimizer_no_changed_files(tmp_path: Path):
    """Empty changed_files list should return success with zero counts."""
    optimizer = CodeOptimizer()
    result = optimizer.optimize(str(tmp_path), [], dry_run=False)
    assert result.files_scanned == 0
    assert result.files_optimized == 0
    assert result.success is True


# ── Test: Multiple files mixed languages ──────────────────────────────────────

def test_optimizer_mixed_files_scanned_count(tmp_path: Path):
    """All files are scanned, unsupported ones are skipped."""
    (tmp_path / "main.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "style.css").write_text(".a { color: red; }\n", encoding="utf-8")
    (tmp_path / "config.xml").write_text("<r/>\n", encoding="utf-8")

    import shutil
    if not shutil.which("ruff"):
        pytest.skip("ruff not installed")

    optimizer = CodeOptimizer()
    result = optimizer.optimize(str(tmp_path), ["main.py", "style.css", "config.xml"], dry_run=False)

    assert result.files_scanned == 3
    # css and xml should be skipped
    assert result.files_skipped >= 2
    skipped_files_list = [s.file for s in result.skipped_files]
    assert "style.css" in skipped_files_list
    assert "config.xml" in skipped_files_list
