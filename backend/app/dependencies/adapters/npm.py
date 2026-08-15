import json
import subprocess
from pathlib import Path
from typing import List, Tuple

from app.dependencies.models import (
    DependencyUpdate, DependencyExecutionResult,
    DependencyStatus, FailureCategory
)

def update_npm(workspace_path: str, updates: List[DependencyUpdate]) -> Tuple[List[DependencyExecutionResult], List[str]]:
    results = []
    changed_files = set()
    
    # 1. Update package.json
    for u in updates:
        abs_manifest = Path(workspace_path) / u.manifest_file
        if not abs_manifest.exists():
            results.append(DependencyExecutionResult(
                update=u,
                status=DependencyStatus.FAILED,
                failure_category=FailureCategory.SOURCE_FAILURE,
                error_message=f"Manifest {u.manifest_file} not found."
            ))
            continue
            
        try:
            data = json.loads(abs_manifest.read_text(encoding="utf-8"))
            updated = False
            for section in ["dependencies", "devDependencies", "peerDependencies"]:
                if section in data and u.package in data[section]:
                    data[section][u.package] = u.target_version
                    updated = True
            
            if updated:
                abs_manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
                changed_files.add(u.manifest_file)
        except Exception as e:
            results.append(DependencyExecutionResult(
                update=u,
                status=DependencyStatus.FAILED,
                failure_category=FailureCategory.SOURCE_FAILURE,
                error_message=str(e)
            ))
            continue

    # 2. Run npm install
    try:
        res = subprocess.run(
            ["npm.cmd", "install", "--no-audit", "--no-fund"],
            cwd=workspace_path,
            capture_output=True,
            text=True
        )
        if res.returncode != 0:
            for u in updates:
                results.append(DependencyExecutionResult(
                    update=u,
                    status=DependencyStatus.FAILED,
                    failure_category=FailureCategory.RESTORE_FAILURE,
                    error_message=res.stderr or res.stdout
                ))
            return results, list(changed_files)
        
        # Check for package-lock.json modification
        lock_file = Path(workspace_path) / "package-lock.json"
        if lock_file.exists():
            changed_files.add("package-lock.json")
            
    except FileNotFoundError:
        for u in updates:
            results.append(DependencyExecutionResult(
                update=u,
                status=DependencyStatus.FAILED,
                failure_category=FailureCategory.ENVIRONMENT_FAILURE,
                error_message="npm command not found"
            ))
        return results, list(changed_files)
        
    # 3. Run validation (npm test if exists)
    try:
        pkg = json.loads((Path(workspace_path) / "package.json").read_text(encoding="utf-8"))
        if "scripts" in pkg and "test" in pkg["scripts"] and "no test specified" not in pkg["scripts"]["test"]:
            res_test = subprocess.run(["npm.cmd", "test"], cwd=workspace_path, capture_output=True, text=True)
            if res_test.returncode != 0:
                for u in updates:
                    results.append(DependencyExecutionResult(
                        update=u,
                        status=DependencyStatus.FAILED,
                        failure_category=FailureCategory.TEST_FAILURE,
                        error_message=res_test.stderr or res_test.stdout
                    ))
                return results, list(changed_files)
    except Exception:
        pass # Ignore missing test script

    # Success
    for u in updates:
        if any(r.update.package == u.package for r in results):
            continue # already failed
        results.append(DependencyExecutionResult(
            update=u,
            status=DependencyStatus.APPLIED
        ))

    return results, list(changed_files)
