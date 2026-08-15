import os
from pathlib import Path
from typing import List
from app.validation.models import ProjectMap, ProjectManifest
from app.validation.project_detector import detect_project, is_ignored_dir

def build_project_map(workspace_root: Path) -> ProjectMap:
    projects = []
    # Find all .sln and .slnx first to help with C# solutions
    solutions = []
    
    for root, dirs, files in os.walk(workspace_root):
        rel_root = Path(root).relative_to(workspace_root)
        if is_ignored_dir(rel_root.parts):
            dirs[:] = []  # Don't recurse into ignored dirs
            continue
            
        for file in files:
            file_path = Path(root) / file
            if file.lower().endswith((".sln", ".slnx")):
                solutions.append(file_path)
            manifest = detect_project(file_path, workspace_root)
            if manifest:
                # We don't want to add duplicate manifests for python if multiple files exist in same dir
                if manifest.project_type == "python":
                    exists = any(p.project_type == "python" and p.project_root == manifest.project_root for p in projects)
                    if exists: continue
                projects.append(manifest)

    # Associate C# projects with solutions if possible
    # We will let command_resolver pick the solution over the csproj
    
    # Also add solutions as projects themselves if they weren't detected
    for sln in solutions:
        manifest_rel = str(sln.relative_to(workspace_root))
        project_id = f"sln_{sln.name}"
        # Only add if not already in there (detect_project doesn't handle sln natively to avoid double counting, but let's add it)
        projects.append(ProjectManifest(
            project_id=project_id,
            manifest_path=manifest_rel,
            project_type="dotnet_solution",
            project_root=str(sln.parent.relative_to(workspace_root)) if sln.parent != workspace_root else ".",
            package_manager="dotnet",
            solution_path=manifest_rel
        ))

    return ProjectMap(
        workspace_root=str(workspace_root),
        projects=projects
    )
