from enum import Enum
from pydantic import BaseModel
from typing import Optional, List

class DependencyStatus(str, Enum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    NOT_APPROVED = "NOT_APPROVED"
    APPLIED = "APPLIED"
    UNCHANGED = "UNCHANGED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"

class FailureCategory(str, Enum):
    NONE = "NONE"
    ENVIRONMENT_FAILURE = "ENVIRONMENT_FAILURE"
    RESOLUTION_FAILURE = "RESOLUTION_FAILURE"
    RESTORE_FAILURE = "RESTORE_FAILURE"
    BUILD_FAILURE = "BUILD_FAILURE"
    TEST_FAILURE = "TEST_FAILURE"
    SOURCE_FAILURE = "SOURCE_FAILURE"

class UpdateRisk(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class UpdateType(str, Enum):
    PATCH = "PATCH"
    MINOR = "MINOR"
    MAJOR = "MAJOR"
    UNKNOWN = "UNKNOWN"

class DependencyUpdate(BaseModel):
    package: str
    package_manager: str
    current_version: str
    target_version: str
    update_type: UpdateType
    risk: UpdateRisk
    reason: str
    manifest_file: str

class DependencyExecutionResult(BaseModel):
    update: DependencyUpdate
    status: DependencyStatus
    failure_category: FailureCategory = FailureCategory.NONE
    error_message: Optional[str] = None
    unified_diff: Optional[str] = None

class BatchExecutionResult(BaseModel):
    workspace_path: str
    success: bool
    results: List[DependencyExecutionResult]
    files_changed: List[str]
    global_error: Optional[str] = None
