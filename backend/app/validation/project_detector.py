import os
from pathlib import Path
from typing import List, Optional, Tuple
from app.validation.models import ProjectManifest

def is_ignored_dir(path_parts: Tuple[str, ...]) -> bool:
    ignored = {".git", "node_modules", "bin", "obj", "dist", "build", ".next", "target", "venv", ".venv", "packages", "vendor"}
    return any(part in ignored for part in path_parts)

def detect_project(file_path: Path, workspace_root: Path) -> Optional[ProjectManifest]:
    if is_ignored_dir(file_path.relative_to(workspace_root).parts[:-1]):
        return None

    filename = file_path.name.lower()
    project_type = None
    package_manager = None
    solution_path = None

    if filename in ["package.json"]:
        project_type = "node"
        package_manager = "npm"
        # Check yarn/pnpm
        if (file_path.parent / "yarn.lock").exists():
            package_manager = "yarn"
        elif (file_path.parent / "pnpm-lock.yaml").exists():
            package_manager = "pnpm"
            
    elif filename.endswith(".csproj") or filename.endswith(".fsproj") or filename.endswith(".vbproj"):
        project_type = "dotnet"
        package_manager = "dotnet"
        # Solution path will be resolved at the workspace level
        
    elif filename in ["pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini", "requirements.txt"]:
        project_type = "python"
        package_manager = "pip"
        
    elif filename in ["pom.xml"]:
        project_type = "java"
        package_manager = "mvn"
        
    elif filename in ["build.gradle", "build.gradle.kts"]:
        project_type = "gradle"
        package_manager = "gradle"
        
    else:
        return None

    # Detect wrappers
    wrappers = []
    if project_type == "java" and package_manager == "mvn":
        if (file_path.parent / "mvnw").exists(): wrappers.append("mvnw")
        if (file_path.parent / "mvnw.cmd").exists(): wrappers.append("mvnw.cmd")
    elif project_type == "gradle":
        if (file_path.parent / "gradlew").exists(): wrappers.append("gradlew")
        if (file_path.parent / "gradlew.bat").exists(): wrappers.append("gradlew.bat")

    manifest_rel = str(file_path.relative_to(workspace_root))
    project_id = file_path.parent.name if file_path.parent.name else "root"
    # To make project_id unique
    project_id = f"{project_id}_{file_path.name}"

    return ProjectManifest(
        project_id=project_id,
        manifest_path=manifest_rel,
        project_type=project_type,
        project_root=str(file_path.parent.relative_to(workspace_root)) if file_path.parent != workspace_root else ".",
        package_manager=package_manager,
        available_wrappers=wrappers
    )
