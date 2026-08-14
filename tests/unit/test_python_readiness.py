"""Regression tests: Python adapter readiness must detect Ruff inside the project
virtualenv (.venv/Scripts/ruff.exe, .venv/bin/ruff) and prefer it over global PATH."""
import sys
from pathlib import Path
from unittest.mock import patch

from app.adapters.python.adapter import PythonRuffAdapter


def _check_readiness(workspace: Path, fake_bin: Path, ruff_on_path=None, python_on_path="python"):
    def _which(name):
        if name == "ruff":
            return ruff_on_path
        return python_on_path

    adapter = PythonRuffAdapter()
    with patch.object(sys, "executable", str(fake_bin / "python.exe")), patch("shutil.which", side_effect=_which):
        return adapter.check_environment_readiness(str(workspace))


def test_ruff_available_in_windows_venv(tmp_path: Path):
    fake_bin = tmp_path / "fake-bin"
    ruff = tmp_path / ".venv" / "Scripts" / "ruff.exe"
    ruff.parent.mkdir(parents=True)
    ruff.write_bytes(b"#! fake windows ruff")

    readiness = _check_readiness(tmp_path, fake_bin)
    assert readiness["ready"] is True
    assert readiness["missing_tools"] == []


def test_ruff_available_in_unix_venv(tmp_path: Path):
    fake_bin = tmp_path / "fake-bin"
    ruff = tmp_path / ".venv" / "bin" / "ruff"
    ruff.parent.mkdir(parents=True)
    ruff.write_bytes(b"#!/usr/bin/env sh")

    readiness = _check_readiness(tmp_path, fake_bin)
    assert readiness["ready"] is True
    assert readiness["missing_tools"] == []


def test_ruff_available_globally_on_path(tmp_path: Path):
    fake_bin = tmp_path / "fake-bin"
    readiness = _check_readiness(tmp_path, fake_bin, ruff_on_path="/opt/ruff/ruff")

    assert readiness["ready"] is True
    assert readiness["missing_tools"] == []


def test_ruff_unavailable(tmp_path: Path):
    fake_bin = tmp_path / "fake-bin"
    readiness = _check_readiness(tmp_path, fake_bin, ruff_on_path=None)

    assert readiness["ready"] is False
    assert "ruff" in readiness["missing_tools"]


def test_venv_ruff_preferred_over_global_path(tmp_path: Path):
    fake_bin = tmp_path / "fake-bin"
    venv_ruff = tmp_path / ".venv" / "Scripts" / "ruff.exe"
    venv_ruff.parent.mkdir(parents=True)
    venv_ruff.write_bytes(b"#! fake")

    adapter = PythonRuffAdapter()
    with patch.object(sys, "executable", str(fake_bin / "python.exe")), patch("shutil.which", side_effect=lambda name: "/opt/ruff/ruff" if name == "ruff" else "python"):
        resolved = adapter._resolve_ruff(str(tmp_path))

    assert resolved == str(venv_ruff)