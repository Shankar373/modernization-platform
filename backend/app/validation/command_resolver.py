import sys
import json
import os
from pathlib import Path
from app.validation.models import ProjectMap, ValidationCommand

def resolve_commands(project_map: ProjectMap) -> ProjectMap:
    workspace_root = Path(project_map.workspace_root)
    
    solutions = [p for p in project_map.projects if p.project_type == "dotnet_solution"]
    solution_dirs = {p.project_root: p for p in solutions}
    
    resolved_projects = []
    
    for project in project_map.projects:
        build_cmds = []
        test_cmds = []
        
        abs_root = workspace_root / project.project_root
        
        if project.project_type == "node":
            pkg_path = workspace_root / project.manifest_path
            try:
                with open(pkg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    scripts = data.get("scripts", {})
                    
                    if "build" in scripts:
                        cmd = ["npm.cmd", "run", "build"] if os.name == "nt" else ["npm", "run", "build"]
                        if project.package_manager == "yarn":
                            cmd = ["yarn.cmd", "run", "build"] if os.name == "nt" else ["yarn", "run", "build"]
                        elif project.package_manager == "pnpm":
                            cmd = ["pnpm.cmd", "run", "build"] if os.name == "nt" else ["pnpm", "run", "build"]
                            
                        build_cmds.append(ValidationCommand(command=cmd, working_directory=project.project_root, command_type="build", tool=project.package_manager))
                        
                    if "test" in scripts:
                        cmd = ["npm.cmd", "test"] if os.name == "nt" else ["npm", "test"]
                        if project.package_manager == "yarn":
                            cmd = ["yarn.cmd", "test"] if os.name == "nt" else ["yarn", "test"]
                        elif project.package_manager == "pnpm":
                            cmd = ["pnpm.cmd", "test"] if os.name == "nt" else ["pnpm", "test"]
                        test_cmds.append(ValidationCommand(command=cmd, working_directory=project.project_root, command_type="test", tool=project.package_manager))
                        
            except Exception:
                pass
                
        elif project.project_type == "dotnet":
            if project.project_root in solution_dirs:
                continue
                
            cmd = ["dotnet", "build", project.manifest_path]
            build_cmds.append(ValidationCommand(command=cmd, working_directory=".", command_type="build", tool="dotnet"))
            
        elif project.project_type == "dotnet_solution":
            cmd = ["dotnet", "build", project.manifest_path]
            build_cmds.append(ValidationCommand(command=cmd, working_directory=".", command_type="build", tool="dotnet"))
            
        elif project.project_type == "python":
            has_tests = False
            if (abs_root / "tests").exists() or (abs_root / "test").exists():
                has_tests = True
            else:
                try:
                    has_tests = any(f.name.startswith("test_") or f.name.endswith("_test.py") for f in abs_root.rglob("*.py"))
                except Exception:
                    pass
                
            if has_tests:
                test_cmds.append(ValidationCommand(command=[sys.executable, "-m", "pytest"], working_directory=project.project_root, command_type="test", tool="python"))
                
        elif project.project_type == "java":
            tool = "mvn.cmd" if os.name == "nt" else "mvn"
            if "mvnw.cmd" in project.available_wrappers and os.name == "nt":
                tool = "mvnw.cmd"
                cmd = [f".\\{tool}"]
            elif "mvnw" in project.available_wrappers and os.name != "nt":
                tool = "mvnw"
                cmd = [f"./{tool}"]
            else:
                cmd = [tool]
                
            cmd.append("compile")
            build_cmds.append(ValidationCommand(command=cmd, working_directory=project.project_root, command_type="build", tool=tool))
            
        elif project.project_type == "gradle":
            tool = "gradlew.bat" if os.name == "nt" else "gradle"
            if "gradlew.bat" in project.available_wrappers and os.name == "nt":
                tool = "gradlew.bat"
                cmd = [f".\\{tool}"]
            elif "gradlew" in project.available_wrappers and os.name != "nt":
                tool = "gradlew"
                cmd = [f"./{tool}"]
            else:
                tool = "gradle"
                cmd = [tool]
                
            cmd.append("classes")
            build_cmds.append(ValidationCommand(command=cmd, working_directory=project.project_root, command_type="build", tool=tool))

        project.build_commands = build_cmds
        project.test_commands = test_cmds
        resolved_projects.append(project)

    project_map.projects = resolved_projects
    return project_map
