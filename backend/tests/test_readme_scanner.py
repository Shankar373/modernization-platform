import pytest
from pathlib import Path
from app.discovery.scanner import UniversalScanner
from app.core.domain.models import DetectedDocumentation, DocItem, TechnologyProfile


def test_readme_scanner_empty_workspace(tmp_path):
    scanner = UniversalScanner()
    profile = scanner.scan(str(tmp_path))
    assert profile.documentation is None


def test_readme_scanner_single_root_readme(tmp_path):
    readme_content = """# Legacy Enterprise App
This is a legacy .NET Framework 4.8 application running on Windows Server with IIS.

## Requirements
- Windows Server 2019
- IIS 10.0
- SQL Server 2017

## Environment
PORT=8080
DATABASE_URL=Server=myServerAddress;Database=myDataBase;Uid=myUsername;Pwd=myPassword;
JWT_SECRET=supersecretkey12345

## Build & Run Instructions
```cmd
msbuild LegacyApp.sln /p:Configuration=Release
```

```powershell
dotnet run --project src/LegacyApp.csproj
```

Run tests:
```bash
pytest tests/ -v
```
"""
    (tmp_path / "README.md").write_text(readme_content, encoding="utf-8")
    (tmp_path / "Program.cs").write_text("using System; namespace App { class Program { static void Main() {} } }", encoding="utf-8")

    scanner = UniversalScanner()
    profile = scanner.scan(str(tmp_path))

    assert profile.documentation is not None
    doc: DetectedDocumentation = profile.documentation
    assert doc.total_docs_found == 1
    assert doc.primary_readme is not None
    assert doc.primary_readme.is_root is True
    assert doc.primary_readme.file_name == "README.md"

    # Test extracted servers
    assert "IIS" in doc.all_servers

    # Test extracted databases
    assert "SQL Server" in doc.all_databases

    # Test extracted env vars
    assert any("DATABASE_URL" in env for env in doc.all_env_vars)
    assert any("JWT_SECRET" in env for env in doc.all_env_vars)

    # Test extracted commands
    assert any("msbuild" in cmd.lower() for cmd in doc.all_build_commands)
    assert any("dotnet run" in cmd.lower() for cmd in doc.all_run_commands)
    assert any("pytest" in cmd.lower() for cmd in doc.all_test_commands)


def test_readme_scanner_monorepo_discovery(tmp_path):
    # Root README
    (tmp_path / "README.md").write_text("""# Monorepo Platform
Contains multiple services. Uses Docker Compose and Kubernetes.
""", encoding="utf-8")

    # Backend service
    backend_dir = tmp_path / "services" / "backend"
    backend_dir.mkdir(parents=True, exist_ok=True)
    (backend_dir / "README.md").write_text("""# Backend Service
Built with Java 17 and Apache Tomcat.
Uses PostgreSQL and Redis for caching.

```bash
mvn clean package
```

```bash
java -jar target/app.jar
```
""", encoding="utf-8")

    # Frontend app
    frontend_dir = tmp_path / "apps" / "frontend"
    frontend_dir.mkdir(parents=True, exist_ok=True)
    (frontend_dir / "README.md").write_text("""# Frontend App
Built with React and Nginx.

```bash
npm run build
```

```bash
npm start
```
""", encoding="utf-8")

    scanner = UniversalScanner()
    profile = scanner.scan(str(tmp_path))

    assert profile.documentation is not None
    doc: DetectedDocumentation = profile.documentation

    # Monorepo should detect root + 2 subprojects
    assert doc.total_docs_found == 3
    assert doc.primary_readme.is_root is True
    assert len(doc.subproject_readmes) == 2

    # Aggregated signals across monorepo
    assert "Docker Compose" in doc.all_servers or "Kubernetes" in doc.all_servers
    assert "Apache Tomcat" in doc.all_servers
    assert "Nginx" in doc.all_servers
    assert "PostgreSQL" in doc.all_databases
    assert "Redis" in doc.all_databases

    assert any("mvn" in cmd for cmd in doc.all_build_commands)
    assert any("npm run build" in cmd for cmd in doc.all_build_commands)
    assert any("npm start" in cmd for cmd in doc.all_run_commands)


def test_readme_scanner_large_file_cap(tmp_path):
    # Giant README file (> 60KB)
    giant_content = "# Big Doc\n" + ("Line with some content.\n" * 4000)
    (tmp_path / "README.txt").write_text(giant_content, encoding="utf-8")

    scanner = UniversalScanner()
    profile = scanner.scan(str(tmp_path))

    assert profile.documentation is not None
    # Ensure preview is capped at 50,000 chars
    assert len(profile.documentation.primary_readme.content_preview) <= 50000
