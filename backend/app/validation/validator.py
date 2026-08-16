import os
import shutil
import subprocess
from pathlib import Path
from app.validation.models import ValidationCommand, ValidationResult, ValidationStatus, FailureCategory, ProjectManifest

def is_tool_available(tool: str, working_dir: Path) -> bool:
    if tool.startswith(".\\") or tool.startswith("./"):
        wrapper_path = working_dir / tool[2:]
        return wrapper_path.exists()
    return shutil.which(tool) is not None

def classify_error(output: str, project_type: str) -> FailureCategory:
    lower_out = output.lower()
    if project_type in ["dotnet", "dotnet_solution"]:
        if any(code.lower() in lower_out for code in [
            "msb3644", "msb4019", "msb1003", "netsdk1004", "netsdk1005",
            "net6.0-windows", "the imported project", "was not found"
        ]):
            return FailureCategory.ENVIRONMENT
    elif project_type == "node":
        if any(err in lower_out for err in [
            "cannot find module", "err_pnpm_no_matching_version", "missing dependencies",
            "command not found", "is not recognized as an internal or external command",
            "node_modules", "npm err!", "pnpm err!", "yarn err!", "enoent", "sh: 1:",
            "elockverifynotmet", "err_pnpm_outdated_lockfile"
        ]):
            return FailureCategory.ENVIRONMENT
    elif project_type == "python":
        if any(err in lower_out for err in [
            "modulenotfounderror", "no module named", "pytest: command not found",
            "pytest is not recognized", "importerror", "tool_missing"
        ]):
            return FailureCategory.ENVIRONMENT
    elif project_type in ["java", "gradle"]:
        if any(err in lower_out for err in [
            "could not resolve dependencies", "plugin not found", "java_home is not set",
            "is not recognized as an internal or external command"
        ]):
            return FailureCategory.ENVIRONMENT
    return FailureCategory.BUILD_FAILURE

def run_validation(project: ProjectManifest, cmd_def: ValidationCommand, workspace_root: str) -> ValidationResult:
    abs_wd = Path(workspace_root) / cmd_def.working_directory
    
    # Auto-restore node_modules if missing
    if project.project_type == "node" and not (abs_wd / "node_modules").exists() and not (Path(workspace_root) / "node_modules").exists():
        restore_tool = "pnpm.cmd" if (project.package_manager == "pnpm" and is_tool_available("pnpm.cmd", abs_wd)) else ("npm.cmd" if os.name == "nt" else "npm")
        if is_tool_available(restore_tool, abs_wd):
            try:
                subprocess.run(
                    [restore_tool, "install"],
                    cwd=str(abs_wd),
                    capture_output=True,
                    text=True,
                    timeout=60
                )
            except Exception:
                pass

        if not (abs_wd / "node_modules").exists() and not (Path(workspace_root) / "node_modules").exists():
            return ValidationResult(
                project=project.project_id,
                project_type=project.project_type,
                command=" ".join(cmd_def.command),
                status=ValidationStatus.ENVIRONMENT_BLOCKED,
                category=FailureCategory.ENVIRONMENT,
                message="Node.js dependencies ('node_modules') could not be automatically restored in sandbox."
            )
    
    if not is_tool_available(cmd_def.tool, abs_wd):
        return ValidationResult(
            project=project.project_id,
            project_type=project.project_type,
            command=" ".join(cmd_def.command),
            status=ValidationStatus.ENVIRONMENT_BLOCKED,
            category=FailureCategory.TOOL_MISSING,
            message=f"Required tool '{cmd_def.tool}' is missing or not executable on host environment."
        )
        
    try:
        res = subprocess.run(
            cmd_def.command,
            cwd=str(abs_wd),
            capture_output=True,
            text=True,
            timeout=120
        )
        
        output = res.stdout + "\n" + res.stderr
        
        if res.returncode == 0:
            return ValidationResult(
                project=project.project_id,
                project_type=project.project_type,
                command=" ".join(cmd_def.command),
                status=ValidationStatus.PASS,
                exit_code=0,
                message=output
            )
        else:
            category = classify_error(output, project.project_type)
            status = ValidationStatus.ENVIRONMENT_BLOCKED if category == FailureCategory.ENVIRONMENT else ValidationStatus.FAIL
            return ValidationResult(
                project=project.project_id,
                project_type=project.project_type,
                command=" ".join(cmd_def.command),
                status=status,
                exit_code=res.returncode,
                category=category,
                message=output
            )
            
    except subprocess.TimeoutExpired:
        return ValidationResult(
            project=project.project_id,
            project_type=project.project_type,
            command=" ".join(cmd_def.command),
            status=ValidationStatus.FAIL,
            category=FailureCategory.BUILD_FAILURE,
            message="Command timed out after 120 seconds."
        )
    except Exception as e:
        return ValidationResult(
            project=project.project_id,
            project_type=project.project_type,
            command=" ".join(cmd_def.command),
            status=ValidationStatus.FAIL,
            category=FailureCategory.UNKNOWN,
            message=f"Execution failed: {str(e)}"
        )
