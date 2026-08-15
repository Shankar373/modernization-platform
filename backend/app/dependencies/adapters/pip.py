import subprocess
import re
from pathlib import Path
from typing import List, Tuple

from app.dependencies.models import (
    DependencyUpdate, DependencyExecutionResult,
    DependencyStatus, FailureCategory
)

def update_pip(workspace_path: str, updates: List[DependencyUpdate]) -> Tuple[List[DependencyExecutionResult], List[str]]:
    results = []
    changed_files = set()
    
    for u in updates:
        abs_manifest = Path(workspace_path) / u.manifest_file
        if not abs_manifest.exists():
            results.append(DependencyExecutionResult(
                update=u, status=DependencyStatus.FAILED,
                failure_category=FailureCategory.SOURCE_FAILURE,
                error_message=f"Manifest {u.manifest_file} not found."
            ))
            continue
            
        file_name = abs_manifest.name.lower()
        try:
            if "requirements" in file_name:
                lines = abs_manifest.read_text(encoding="utf-8").splitlines(keepends=True)
                updated = False
                new_lines = []
                for line in lines:
                    if re.match(rf"^{re.escape(u.package)}([>=<~]=?|===|!=).*$", line, re.IGNORECASE):
                        new_lines.append(f"{u.package}=={u.target_version}\n")
                        updated = True
                    else:
                        new_lines.append(line)
                
                if updated:
                    abs_manifest.write_text("".join(new_lines), encoding="utf-8")
                    changed_files.add(u.manifest_file)
                    
            elif file_name == "pyproject.toml":
                try:
                    import tomlkit
                    doc_content = abs_manifest.read_text(encoding="utf-8")
                    doc = tomlkit.parse(doc_content)
                    updated = False
                    
                    if "tool" in doc and "poetry" in doc["tool"]:
                        for sec in ["dependencies", "dev-dependencies", "group"]:
                            if sec in doc["tool"]["poetry"]:
                                if sec == "group":
                                    for g in doc["tool"]["poetry"]["group"].values():
                                        if "dependencies" in g and u.package in g["dependencies"]:
                                            if isinstance(g["dependencies"][u.package], dict):
                                                g["dependencies"][u.package]["version"] = u.target_version
                                            else:
                                                g["dependencies"][u.package] = u.target_version
                                            updated = True
                                elif u.package in doc["tool"]["poetry"][sec]:
                                    if isinstance(doc["tool"]["poetry"][sec][u.package], dict):
                                        doc["tool"]["poetry"][sec][u.package]["version"] = u.target_version
                                    else:
                                        doc["tool"]["poetry"][sec][u.package] = u.target_version
                                    updated = True
                    
                    if "project" in doc and "dependencies" in doc["project"]:
                        deps = doc["project"]["dependencies"]
                        for i, d in enumerate(deps):
                            if re.match(rf"^{re.escape(u.package)}([>=<~]=?|===|!=).*$", d, re.IGNORECASE):
                                deps[i] = f"{u.package}=={u.target_version}"
                                updated = True
                    
                    if updated:
                        abs_manifest.write_text(tomlkit.dumps(doc), encoding="utf-8")
                        changed_files.add(u.manifest_file)
                except ImportError:
                    pass
        except Exception as e:
            results.append(DependencyExecutionResult(
                update=u, status=DependencyStatus.FAILED,
                failure_category=FailureCategory.SOURCE_FAILURE, error_message=str(e)
            ))
            continue

    for u in updates:
        if any(r.update.package == u.package for r in results):
            continue
            
        file_name = u.manifest_file.lower()
        if "requirements" in file_name:
            cmd = f"pip install -r {u.manifest_file}"
        elif file_name == "pyproject.toml":
            cmd = f"poetry update {u.package}"
        else:
            continue
            
        try:
            res = subprocess.run(cmd, cwd=workspace_path, shell=True, capture_output=True, text=True)
            if res.returncode != 0:
                results.append(DependencyExecutionResult(
                    update=u, status=DependencyStatus.FAILED,
                    failure_category=FailureCategory.RESTORE_FAILURE,
                    error_message=res.stderr or res.stdout
                ))
            else:
                if file_name == "pyproject.toml":
                    lock_file = Path(workspace_path) / "poetry.lock"
                    if lock_file.exists():
                        changed_files.add("poetry.lock")
        except FileNotFoundError:
            results.append(DependencyExecutionResult(
                update=u, status=DependencyStatus.FAILED,
                failure_category=FailureCategory.ENVIRONMENT_FAILURE,
                error_message=f"{cmd} command not found"
            ))

    try:
        res_test = subprocess.run("pytest", cwd=workspace_path, shell=True, capture_output=True, text=True)
        if res_test.returncode != 0 and "not recognized" not in res_test.stderr and "not found" not in res_test.stderr:
            for u in updates:
                if not any(r.update.package == u.package for r in results):
                    results.append(DependencyExecutionResult(
                        update=u, status=DependencyStatus.FAILED,
                        failure_category=FailureCategory.TEST_FAILURE,
                        error_message=res_test.stderr or res_test.stdout
                    ))
    except FileNotFoundError:
        pass 
        
    for u in updates:
        if not any(r.update.package == u.package for r in results):
            results.append(DependencyExecutionResult(update=u, status=DependencyStatus.APPLIED))
            
    return results, list(changed_files)
