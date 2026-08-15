import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Tuple

from app.dependencies.models import (
    DependencyUpdate, DependencyExecutionResult,
    DependencyStatus, FailureCategory
)

def update_nuget(workspace_path: str, updates: List[DependencyUpdate]) -> Tuple[List[DependencyExecutionResult], List[str]]:
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
            
        try:
            # We use string replace to preserve exact formatting since ET strips formatting
            content = abs_manifest.read_text(encoding="utf-8")
            import re
            # Match <PackageReference Include="PackageName" Version="1.2.3" />
            # Match <PackageReference Include="PackageName"><Version>1.2.3</Version></PackageReference>
            
            updated_content = re.sub(
                rf'(<PackageReference[^>]*Include\s*=\s*"{re.escape(u.package)}"[^>]*Version\s*=\s*")[^"]+(")',
                rf'\g<1>{u.target_version}\g<2>',
                content, flags=re.IGNORECASE
            )
            updated_content = re.sub(
                rf'(<PackageReference[^>]*Include\s*=\s*"{re.escape(u.package)}"[^>]*>\s*<Version>)[^<]+(</Version>)',
                rf'\g<1>{u.target_version}\g<2>',
                updated_content, flags=re.IGNORECASE
            )
            
            if updated_content != content:
                abs_manifest.write_text(updated_content, encoding="utf-8")
                changed_files.add(u.manifest_file)
        except Exception as e:
            results.append(DependencyExecutionResult(
                update=u, status=DependencyStatus.FAILED,
                failure_category=FailureCategory.SOURCE_FAILURE, error_message=str(e)
            ))
            continue
            
    # Restore & Build
    try:
        # Run dotnet restore and dotnet build on the workspace or specific csproj files
        res_restore = subprocess.run(["dotnet", "restore"], cwd=workspace_path, capture_output=True, text=True)
        if res_restore.returncode != 0:
            for u in updates:
                if not any(r.update.package == u.package for r in results):
                    results.append(DependencyExecutionResult(
                        update=u, status=DependencyStatus.FAILED,
                        failure_category=FailureCategory.RESTORE_FAILURE,
                        error_message=res_restore.stderr or res_restore.stdout
                    ))
            return results, list(changed_files)
            
        res_build = subprocess.run(["dotnet", "build", "--no-restore"], cwd=workspace_path, capture_output=True, text=True)
        if res_build.returncode != 0:
            for u in updates:
                if not any(r.update.package == u.package for r in results):
                    results.append(DependencyExecutionResult(
                        update=u, status=DependencyStatus.FAILED,
                        failure_category=FailureCategory.BUILD_FAILURE,
                        error_message=res_build.stderr or res_build.stdout
                    ))
            return results, list(changed_files)
    except FileNotFoundError:
        for u in updates:
            if not any(r.update.package == u.package for r in results):
                results.append(DependencyExecutionResult(
                    update=u, status=DependencyStatus.FAILED,
                    failure_category=FailureCategory.ENVIRONMENT_FAILURE,
                    error_message="dotnet command not found"
                ))
        return results, list(changed_files)
        
    for u in updates:
        if not any(r.update.package == u.package for r in results):
            results.append(DependencyExecutionResult(update=u, status=DependencyStatus.APPLIED))
            
    return results, list(changed_files)
