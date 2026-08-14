import pytest
import os
import tempfile
from pathlib import Path
from backend.app.discovery.scanner import UniversalScanner

def test_language_detection_python():
    scanner = UniversalScanner()
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create Python files and markers
        Path(tmpdir, "main.py").write_text("import os\nprint('hello')")
        Path(tmpdir, "requirements.txt").write_text("fastapi==0.111.0\nuvicorn==0.30.1")
        
        profile = scanner.scan(tmpdir)
        
        languages = [l.name for l in profile.languages]
        assert "Python" in languages
        
        # Verify dependencies are parsed
        dep_names = [d.name for d in profile.dependencies]
        assert "fastapi" in dep_names
        assert "uvicorn" in dep_names

def test_language_detection_java():
    scanner = UniversalScanner()
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create Java files and markers
        Path(tmpdir, "pom.xml").write_text("<project><java.version>11</java.version></project>")
        java_dir = Path(tmpdir, "src/main/java")
        java_dir.mkdir(parents=True)
        Path(java_dir, "App.java").write_text("package com.test;\npublic class App {}")
        
        profile = scanner.scan(tmpdir)
        
        languages = [l.name for l in profile.languages]
        assert "Java" in languages
        
        java_lang = next(l for l in profile.languages if l.name == "Java")
        assert java_lang.version == "Java 11"
