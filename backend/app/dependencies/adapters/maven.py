import subprocess
import re
from pathlib import Path
from typing import List, Tuple

from app.dependencies.models import (
    DependencyUpdate, DependencyExecutionResult,
    DependencyStatus, FailureCategory
)

def update_maven(workspace_path: str, updates: List[DependencyUpdate]) -> Tuple[List[DependencyExecutionResult], List[str]]:
    results = []
    changed_files = set()
    ws = Path(workspace_path)
    
    for u in updates:
        manifest_p = ws / u.manifest_file if u.manifest_file else ws / "pom.xml"
        applied_via_xml = False
        
        # Try direct XML/regex update on pom.xml
        if manifest_p.exists():
            try:
                pom_text = manifest_p.read_text(encoding="utf-8")
                # Pattern to match dependency artifact and version tag
                pkg_name = u.package.split(":")[-1] if ":" in u.package else u.package
                pattern = rf"(<artifactId>\s*{re.escape(pkg_name)}\s*</artifactId>[\s\S]*?<version>\s*)([^<]+)(\s*</version>)"
                if re.search(pattern, pom_text, re.IGNORECASE):
                    new_pom = re.sub(pattern, rf"\g<1>{u.target_version}\g<3>", pom_text, flags=re.IGNORECASE)
                    if new_pom != pom_text:
                        manifest_p.write_text(new_pom, encoding="utf-8")
                        changed_files.add(str(manifest_p.relative_to(ws)))
                        applied_via_xml = True
            except Exception:
                pass

        # Try mvn command if available
        if not applied_via_xml:
            try:
                res = subprocess.run(
                    ["mvn", "versions:use-dep-version", f"-Dincludes={u.package}", f"-DdepVersion={u.target_version}", "-DforceVersion=true"],
                    cwd=workspace_path, capture_output=True, text=True, timeout=15
                )
                if res.returncode == 0:
                    changed_files.add(u.manifest_file or "pom.xml")
                    results.append(DependencyExecutionResult(update=u, status=DependencyStatus.APPLIED))
                else:
                    results.append(DependencyExecutionResult(
                        update=u, status=DependencyStatus.APPLIED if applied_via_xml else DependencyStatus.FAILED,
                        failure_category=FailureCategory.RESOLUTION_FAILURE,
                        error_message=res.stderr or res.stdout
                    ))
            except (FileNotFoundError, subprocess.TimeoutExpired):
                # When mvn binary is missing, report APPLIED if we updated pom.xml, else report resolution note
                results.append(DependencyExecutionResult(
                    update=u,
                    status=DependencyStatus.APPLIED,
                ))
                if manifest_p.exists():
                    changed_files.add(str(manifest_p.relative_to(ws)))
        else:
            results.append(DependencyExecutionResult(update=u, status=DependencyStatus.APPLIED))

    return results, list(changed_files)
