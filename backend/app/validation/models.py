from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ValidationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    ENVIRONMENT_BLOCKED = "ENVIRONMENT_BLOCKED"
    PRE_EXISTING_FAILURE = "PRE_EXISTING_FAILURE"
    MODERNIZATION_REGRESSION = "MODERNIZATION_REGRESSION"
    OPTIMIZATION_REGRESSION = "OPTIMIZATION_REGRESSION"
    SKIPPED = "SKIPPED"

class FailureCategory(str, Enum):
    SOURCE = "SOURCE"
    ENVIRONMENT = "ENVIRONMENT"
    CONFIGURATION = "CONFIGURATION"
    TOOL_MISSING = "TOOL_MISSING"
    TEST_FAILURE = "TEST_FAILURE"
    BUILD_FAILURE = "BUILD_FAILURE"
    RESTORE_FAILURE = "RESTORE_FAILURE"
    UNKNOWN = "UNKNOWN"

class ValidationCommand(BaseModel):
    command: List[str]
    working_directory: str
    command_type: str  # "build", "test", "restore", etc.
    tool: str

class ProjectManifest(BaseModel):
    project_id: str  # Unique identifier, e.g., "frontend", "backend"
    manifest_path: str  # Relative path to package.json, .csproj, etc.
    project_type: str  # "dotnet", "node", "python", "java", "gradle"
    project_root: str  # Directory containing the manifest
    solution_path: Optional[str] = None  # For .NET
    package_manager: str  # "npm", "yarn", "pip", "mvn", "gradle", "dotnet"
    available_wrappers: List[str] = Field(default_factory=list)
    build_commands: List[ValidationCommand] = Field(default_factory=list)
    test_commands: List[ValidationCommand] = Field(default_factory=list)

class ProjectMap(BaseModel):
    workspace_root: str
    projects: List[ProjectManifest] = Field(default_factory=list)

class ValidationResult(BaseModel):
    project: str  # Name or path
    project_type: str
    command: str
    status: ValidationStatus
    exit_code: Optional[int] = None
    category: Optional[FailureCategory] = None
    message: str
    baseline_status: Optional[ValidationStatus] = None
    modernized_status: Optional[ValidationStatus] = None
    optimized_status: Optional[ValidationStatus] = None

class ValidationSummary(BaseModel):
    workspace_root: str
    results: List[ValidationResult] = Field(default_factory=list)
    total_projects_discovered: int = 0
    commands_resolved: int = 0
    not_applicable: int = 0
    environment_blocked: int = 0
    pre_existing_failures: int = 0
    modernization_regressions: int = 0
    optimization_regressions: int = 0
    successful_validations: int = 0
