"""Domain entities for the modernization platform."""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

class CapabilityStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    PARTIALLY_AVAILABLE = "PARTIALLY_AVAILABLE"
    ASSESSMENT_ONLY = "ASSESSMENT_ONLY"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class MigrationProfile(str, Enum):
    CONSERVATIVE = "CONSERVATIVE"
    STANDARD = "STANDARD"
    AGGRESSIVE = "AGGRESSIVE"


class MigrationStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIALLY_SUCCESSFUL = "PARTIALLY_SUCCESSFUL"
    FAILED = "FAILED"
    ASSESSMENT_ONLY = "ASSESSMENT_ONLY"
    NOT_SUPPORTED = "NOT_SUPPORTED"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# ── Evidence & Detection ──────────────────────────────────────────────────────

class DetectionEvidence(BaseModel):
    """A piece of evidence that supports a technology detection."""
    file: Optional[str] = None
    pattern: Optional[str] = None
    description: str
    weight: float = 1.0


class DetectedLanguage(BaseModel):
    name: str
    version: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: List[DetectionEvidence] = []


class DetectedFramework(BaseModel):
    name: str
    version: Optional[str] = None
    language: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: List[DetectionEvidence] = []


class DetectedBuildSystem(BaseModel):
    name: str
    version: Optional[str] = None
    language: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: List[DetectionEvidence] = []


class DetectedDependency(BaseModel):
    name: str
    version: Optional[str] = None
    language: str
    scope: Optional[str] = None


# ── Technology Fingerprint ────────────────────────────────────────────────────

class TechnologyProfile(BaseModel):
    """Normalized technology fingerprint for a repository."""
    profile_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scanned_at: datetime = Field(default_factory=datetime.utcnow)

    languages: List[DetectedLanguage] = []
    frameworks: List[DetectedFramework] = []
    build_systems: List[DetectedBuildSystem] = []
    dependencies: List[DetectedDependency] = []
    databases: List[str] = []
    testing_frameworks: List[str] = []
    frontend_technologies: List[str] = []

    file_count: int = 0
    total_lines: int = 0
    is_multi_language: bool = False

    raw_scan_metadata: Dict[str, Any] = {}


# ── Capability ────────────────────────────────────────────────────────────────

class MigrationCapability(BaseModel):
    """A migration capability entry from the capability registry."""
    name: str
    language: str
    provider: str
    status: CapabilityStatus
    source_versions: List[str] = []
    target_versions: List[str] = []
    risk: RiskLevel = RiskLevel.MEDIUM
    description: str = ""
    notes: Optional[str] = None


# ── Migration Plan ────────────────────────────────────────────────────────────

class MigrationTarget(BaseModel):
    language: str
    source_version: Optional[str] = None
    target_version: str
    framework_source: Optional[str] = None
    framework_target: Optional[str] = None


class PlanStep(BaseModel):
    step_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    order: int
    name: str
    description: str
    adapter: str
    capability: str
    risk: RiskLevel = RiskLevel.LOW
    estimated_files: int = 0
    is_reversible: bool = True


class MigrationPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)

    project_id: str
    profile: MigrationProfile = MigrationProfile.CONSERVATIVE
    targets: List[MigrationTarget] = []
    steps: List[PlanStep] = []
    selected_capabilities: List[str] = []
    overall_risk: RiskLevel = RiskLevel.MEDIUM

    dry_run_available: bool = True
    requires_approval: bool = True


# ── Migration Result ──────────────────────────────────────────────────────────

class FileChangeMetadata(BaseModel):
    file: str
    status: str  # MODIFIED | ADDED | DELETED | UNCHANGED
    changes: List[Dict[str, str]] = []
    tools: List[str] = []
    before_content: Optional[str] = None
    after_content: Optional[str] = None
    diff: Optional[str] = None
    original_content: Optional[str] = None
    modernized_content: Optional[str] = None
    optimized_content: Optional[str] = None
    modernization_diff: Optional[str] = None
    optimization_diff: Optional[str] = None
    final_diff: Optional[str] = None


class MigrationStatistics(BaseModel):
    files_scanned: int = 0
    files_unchanged: int = 0
    files_modified: int = 0
    files_added: int = 0
    files_deleted: int = 0
    dependencies_analyzed: int = 0
    dependencies_updated: int = 0
    capabilities_run: int = 0
    build_passed: Optional[bool] = None
    tests_total: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    warnings: int = 0
    manual_remediation_items: int = 0
    files_optimized: int = 0
    files_optimization_skipped: int = 0


class MigrationResult(BaseModel):
    result_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str
    project_id: str
    plan_id: str
    status: MigrationStatus
    completed_at: Optional[datetime] = None

    statistics: MigrationStatistics = MigrationStatistics()
    changed_files: List[FileChangeMetadata] = []
    timeline: List[Dict[str, Any]] = []
    warnings: List[str] = []
    manual_remediation: List[str] = []
    logs: Dict[str, str] = {}
    optimization_result: Optional[Dict[str, Any]] = None

    output_bundle_path: Optional[str] = None


# ── Project ───────────────────────────────────────────────────────────────────

class Project(BaseModel):
    project_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    source_type: str  # "zip" | "git"
    source_path: str
    workspace_path: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    tech_profile: Optional[TechnologyProfile] = None
    capabilities: List[MigrationCapability] = []
    current_plan: Optional[MigrationPlan] = None
    latest_result: Optional[MigrationResult] = None
