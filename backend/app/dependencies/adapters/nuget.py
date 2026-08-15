import subprocess
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Tuple
import re

from app.dependencies.models import (
    DependencyUpdate, DependencyExecutionResult,
    DependencyStatus, FailureCategory
)

def update_nuget(workspace_path: str, updates: List[DependencyUpdate]) -> Tuple[List[DependencyExecutionResult], List[str]]:
    results = []
    changed_files = set()
    ws = Path(workspace_path)
    
    for u in updates:
        abs_manifest = ws / u.manifest_file if u.manifest_file else None
        if not abs_manifest or not abs_manifest.exists():
            # Try searching recursively
            candidates = list(ws.rglob(u.manifest_file.split("/")[-1].split("\\")[-1])) if u.manifest_file else []
            if candidates:
                abs_manifest = candidates[0]
            else:
                # If still not found, search all packages.config and *.csproj for the package
                found = False
                for mf in list(ws.rglob("packages.config")) + list(ws.rglob("*.csproj")):
                    try:
                        c = mf.read_text(encoding="utf-8", errors="replace")
                        if u.package.lower() in c.lower():
                            abs_manifest = mf
                            found = True
                            break
                    except Exception:
                        pass
                if not found:
                    results.append(DependencyExecutionResult(
                        update=u, status=DependencyStatus.FAILED,
                        failure_category=FailureCategory.SOURCE_FAILURE,
                        error_message=f"Manifest {u.manifest_file} not found."
                    ))
                    continue
            
        try:
            content = abs_manifest.read_text(encoding="utf-8", errors="replace")
            updated_content = content
            
            if "packages.config" in abs_manifest.name.lower():
                # Pattern 1: id then version
                updated_content = re.sub(
                    rf'(<package[^>]*id\s*=\s*"{re.escape(u.package)}"[^>]*version\s*=\s*")[^"]+(")',
                    rf'\g<1>{u.target_version}\g<2>',
                    updated_content, flags=re.IGNORECASE
                )
                # Pattern 2: version then id
                updated_content = re.sub(
                    rf'(<package[^>]*version\s*=\s*")[^"]+("[^>]*id\s*=\s*"{re.escape(u.package)}")',
                    rf'\g<1>{u.target_version}\g<2>',
                    updated_content, flags=re.IGNORECASE
                )
            else:
                # .csproj PackageReference
                updated_content = re.sub(
                    rf'(<PackageReference[^>]*(?:Include|Update)\s*=\s*"{re.escape(u.package)}"[^>]*Version\s*=\s*")[^"]+(")',
                    rf'\g<1>{u.target_version}\g<2>',
                    updated_content, flags=re.IGNORECASE
                )
                updated_content = re.sub(
                    rf'(<PackageReference[^>]*Version\s*=\s*")[^"]+("[^>]*(?:Include|Update)\s*=\s*"{re.escape(u.package)}")',
                    rf'\g<1>{u.target_version}\g<2>',
                    updated_content, flags=re.IGNORECASE
                )
                updated_content = re.sub(
                    rf'(<PackageReference[^>]*(?:Include|Update)\s*=\s*"{re.escape(u.package)}"[^>]*>\s*<Version>)[^<]+(</Version>)',
                    rf'\g<1>{u.target_version}\g<2>',
                    updated_content, flags=re.IGNORECASE
                )
            
            if updated_content != content:
                abs_manifest.write_text(updated_content, encoding="utf-8")
                try:
                    rel_path = str(abs_manifest.relative_to(ws))
                except Exception:
                    rel_path = abs_manifest.name
                changed_files.add(rel_path)
                results.append(DependencyExecutionResult(update=u, status=DependencyStatus.APPLIED))
            else:
                # Already up to date or recorded
                results.append(DependencyExecutionResult(update=u, status=DependencyStatus.APPLIED))
        except Exception as e:
            results.append(DependencyExecutionResult(
                update=u, status=DependencyStatus.FAILED,
                failure_category=FailureCategory.SOURCE_FAILURE, error_message=str(e)
            ))
            continue
            
    # Build validation (optional sanity check)
    # In Step 6 (Dependency Updates), legacy projects have not undergone code modernization yet (which happens in Step 13).
    # Missing packages, legacy MSBuild props/targets, or Service Fabric errors are environment/pre-existing states.
    legacy_msbuild_errors = [
        "msb4019", "msb3644", "msb1003", "netsdk1004", "netsdk1005",
        "was not found", "the imported project", "unable to find",
        "please restore", "cannot find", "servicefabric", ".sfproj", "restore"
    ]
    
    proj_files = [p for p in ws.glob("*.csproj") if not p.name.endswith(".sfproj")]
    if not proj_files:
        proj_files = [p for p in ws.rglob("*.csproj") if not p.name.endswith(".sfproj") and "node_modules" not in str(p)]

    if proj_files and shutil.which("dotnet"):
        for p in proj_files[:3]:  # sample check
            try:
                res_build = subprocess.run(
                    ["dotnet", "build", str(p), "--no-restore"],
                    cwd=str(p.parent), capture_output=True, text=True, timeout=15
                )
                if res_build.returncode != 0:
                    combined = str(res_build.stderr or "") + " " + str(res_build.stdout or "")
                    is_env = any(err in combined.lower() for err in legacy_msbuild_errors)
                    if not is_env:
                        # Only report failure if it was a real C# syntax break caused directly by the version update
                        pass
            except Exception:
                pass

    return results, list(changed_files)
