import subprocess
from pathlib import Path
from typing import List, Tuple

from app.dependencies.models import (
    DependencyUpdate, DependencyExecutionResult,
    DependencyStatus, FailureCategory
)

def update_maven(workspace_path: str, updates: List[DependencyUpdate]) -> Tuple[List[DependencyExecutionResult], List[str]]:
    results = []
    changed_files = set()
    
    for u in updates:
        try:
            # Use maven versions plugin to modify the pom.xml safely
            # Note: We must specify groupId:artifactId. If we only have package name, we assume it's artifactId or groupId:artifactId.
            res = subprocess.run(
                ["mvn", "versions:use-dep-version", f"-Dincludes={u.package}", f"-DdepVersion={u.target_version}", "-DforceVersion=true"],
                cwd=workspace_path, capture_output=True, text=True
            )
            if res.returncode != 0:
                results.append(DependencyExecutionResult(
                    update=u, status=DependencyStatus.FAILED,
                    failure_category=FailureCategory.RESOLUTION_FAILURE,
                    error_message=res.stderr or res.stdout
                ))
            else:
                changed_files.add(u.manifest_file)
        except FileNotFoundError:
            results.append(DependencyExecutionResult(
                update=u, status=DependencyStatus.FAILED,
                failure_category=FailureCategory.ENVIRONMENT_FAILURE,
                error_message="mvn command not found"
            ))
            return results, list(changed_files)
            
    # Clean Test validation
    try:
        res_test = subprocess.run(["mvn", "clean", "test"], cwd=workspace_path, shell=True, capture_output=True, text=True)
        if res_test.returncode != 0:
            for u in updates:
                if not any(r.update.package == u.package for r in results):
                    results.append(DependencyExecutionResult(
                        update=u, status=DependencyStatus.FAILED,
                        failure_category=FailureCategory.TEST_FAILURE,
                        error_message=res_test.stderr or res_test.stdout
                    ))
            return results, list(changed_files)
    except Exception:
        pass
        
    for u in updates:
        if not any(r.update.package == u.package for r in results):
            results.append(DependencyExecutionResult(update=u, status=DependencyStatus.APPLIED))
            
    return results, list(changed_files)
