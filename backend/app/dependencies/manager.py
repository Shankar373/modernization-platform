import logging
from typing import List, Dict
from pathlib import Path
import difflib

from app.dependencies.models import (
    DependencyUpdate, DependencyExecutionResult, BatchExecutionResult,
    DependencyStatus, FailureCategory
)


# Import adapters
from app.dependencies.adapters.npm import update_npm
from app.dependencies.adapters.pip import update_pip
from app.dependencies.adapters.nuget import update_nuget
from app.dependencies.adapters.maven import update_maven

log = logging.getLogger(__name__)

def _make_unified_diff(before: str, after: str, file_path: str) -> str:
    diff_lines = list(difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        lineterm="",
    ))
    return "".join(diff_lines)

class DependencyUpdateManager:
    def execute_updates(self, workspace_path: str, approved_updates: List[DependencyUpdate]) -> BatchExecutionResult:
        if not approved_updates:
            return BatchExecutionResult(
                workspace_path=workspace_path,
                success=True,
                results=[],
                files_changed=[]
            )
            
        # Snapshot the original state of ALL files in the workspace (or just known manifests/lockfiles) to produce accurate diffs
        # Since scanning the whole workspace into memory is huge, we will only snapshot files we know might change
        # based on the approved updates.
        manifest_files = {u.manifest_file for u in approved_updates}
        
        # Add common lockfiles to snapshot list just in case
        manifest_files.update(["package-lock.json", "poetry.lock", "yarn.lock"])
        
        snapshot = {}
        for rel_file in manifest_files:
            abs_f = Path(workspace_path) / rel_file
            if abs_f.exists():
                try:
                    snapshot[rel_file] = abs_f.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    pass # skip binary files

        # We use the snapshot dict we just created as our rollback mechanism.
        snapshot_ref = True
            
        results = []
        files_changed = set()
        
        # We group by package manager for batched execution where applicable
        by_manager: Dict[str, List[DependencyUpdate]] = {}
        for u in approved_updates:
            by_manager.setdefault(u.package_manager.lower(), []).append(u)
            
        global_success = True
        
        for pm, updates in by_manager.items():
            try:
                if pm == "npm":
                    res, changed = update_npm(workspace_path, updates)
                elif pm in ("pip", "poetry", "python"):
                    res, changed = update_pip(workspace_path, updates)
                elif pm == "nuget":
                    res, changed = update_nuget(workspace_path, updates)
                elif pm == "maven":
                    res, changed = update_maven(workspace_path, updates)
                else:
                    for u in updates:
                        results.append(DependencyExecutionResult(
                            update=u,
                            status=DependencyStatus.NOT_IMPLEMENTED,
                            failure_category=FailureCategory.ENVIRONMENT_FAILURE,
                            error_message=f"Package manager {pm} is not implemented."
                        ))
                    changed = []
                    res = []
                    global_success = False
                    
                if pm in ("npm", "pip", "poetry", "python", "nuget", "maven"):
                    results.extend(res)
                    for c in changed:
                        files_changed.add(c)
                
                # Check for any failures
                if any(r.status in (DependencyStatus.FAILED, DependencyStatus.ROLLED_BACK) for r in res):
                    global_success = False
            except Exception as e:
                log.exception(f"Exception during {pm} update")
                for u in updates:
                    results.append(DependencyExecutionResult(
                        update=u,
                        status=DependencyStatus.FAILED,
                        failure_category=FailureCategory.ENVIRONMENT_FAILURE,
                        error_message=str(e)
                    ))
                global_success = False
                
        # Rollback if ANY failure occurred within the batch to preserve absolute baseline
        if not global_success and snapshot_ref:
            try:
                for rel_file, orig_content in snapshot.items():
                    abs_f = Path(workspace_path) / rel_file
                    if abs_f.exists():
                        abs_f.write_text(orig_content, encoding='utf-8')
                    else:
                        pass
                
                # Check for newly created files not in snapshot (like package-lock.json)
                for changed_rel in files_changed:
                    if changed_rel not in snapshot:
                        abs_f = Path(workspace_path) / changed_rel
                        if abs_f.exists():
                            abs_f.unlink()
                            
                # Mark applied as rolled back
                for r in results:
                    if r.status == DependencyStatus.APPLIED:
                        r.status = DependencyStatus.ROLLED_BACK
                files_changed = set() # Diff is zero if rolled back
            except Exception as e:
                log.error(f"Failed to rollback dependencies: {e}")
                
        # Generate diffs for modified files
        # A single execution result gets the diffs of ALL changed files relevant to that ecosystem
        # This simplifies UI rendering (we can just show the combined diff for the batch)
        combined_diff = []
        for changed_rel in files_changed:
            abs_f = Path(workspace_path) / changed_rel
            if abs_f.exists():
                after_content = abs_f.read_text(encoding="utf-8")
                before_content = snapshot.get(changed_rel, "")
                if before_content != after_content:
                    diff_str = _make_unified_diff(before_content, after_content, changed_rel)
                    combined_diff.append(diff_str)
                    
        full_diff = "\n".join(combined_diff)
        
        for r in results:
            if r.status == DependencyStatus.APPLIED:
                r.unified_diff = full_diff

        return BatchExecutionResult(
            workspace_path=workspace_path,
            success=global_success,
            results=results,
            files_changed=list(files_changed)
        )
