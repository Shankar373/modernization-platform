"""SQLAlchemy database models for the Modernization Platform."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Boolean, JSON, ForeignKey, Text
from app.db.session import Base


class DBProject(Base):
    __tablename__ = "projects"

    project_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    source_type = Column(String(50), nullable=False)
    source_path = Column(String(1024), nullable=False)
    workspace_path = Column(String(1024), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class DBProjectProfile(Base):
    __tablename__ = "project_profiles"

    profile_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    scanned_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    languages = Column(JSON, nullable=False, default=list)
    frameworks = Column(JSON, nullable=False, default=list)
    build_systems = Column(JSON, nullable=False, default=list)
    dependencies = Column(JSON, nullable=False, default=list)
    databases = Column(JSON, nullable=False, default=list)
    testing_frameworks = Column(JSON, nullable=False, default=list)
    frontend_technologies = Column(JSON, nullable=False, default=list)

    file_count = Column(Integer, default=0, nullable=False)
    total_lines = Column(Integer, default=0, nullable=False)
    is_multi_language = Column(Boolean, default=False, nullable=False)
    raw_scan_metadata = Column(JSON, nullable=False, default=dict)


class DBMigrationPlan(Base):
    __tablename__ = "migration_plans"

    plan_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    profile = Column(String(50), nullable=False)

    targets = Column(JSON, nullable=False, default=list)
    steps = Column(JSON, nullable=False, default=list)
    selected_capabilities = Column(JSON, nullable=False, default=list)
    overall_risk = Column(String(50), nullable=False)

    dry_run_available = Column(Boolean, default=True, nullable=False)
    requires_approval = Column(Boolean, default=True, nullable=False)


class DBMigrationRun(Base):
    __tablename__ = "migration_runs"

    result_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), nullable=False)
    project_id = Column(String(36), ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    plan_id = Column(String(36), ForeignKey("migration_plans.plan_id", ondelete="CASCADE"), nullable=False)
    status = Column(String(50), nullable=False)
    completed_at = Column(DateTime, nullable=True)

    statistics = Column(JSON, nullable=False, default=dict)
    changed_files = Column(JSON, nullable=False, default=list)
    timeline = Column(JSON, nullable=False, default=list)
    warnings = Column(JSON, nullable=False, default=list)
    manual_remediation = Column(JSON, nullable=False, default=list)
    logs = Column(JSON, nullable=False, default=dict)
    output_bundle_path = Column(String(1024), nullable=True)


class DBMigrationStage(Base):
    __tablename__ = "migration_stages"

    stage_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    run_id = Column(String(36), ForeignKey("migration_runs.result_id", ondelete="SET NULL"), nullable=True)
    stage_name = Column(String(100), nullable=False)
    stage_order = Column(Integer, default=0, nullable=False)
    status = Column(String(50), nullable=False)
    start_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    end_time = Column(DateTime, nullable=True)
    duration = Column(Integer, default=0, nullable=False)
    progress = Column(Integer, default=0, nullable=False)
    message = Column(String(512), nullable=True)
    logs = Column(Text, nullable=True)
    structured_results = Column(JSON, nullable=True)
    error_information = Column(Text, nullable=True)


class DBMigrationCheckpoint(Base):
    __tablename__ = "migration_checkpoints"

    checkpoint_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    run_id = Column(String(36), ForeignKey("migration_runs.result_id", ondelete="CASCADE"), nullable=False)
    commit_sha = Column(String(100), nullable=False)
    description = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class DBRecipeExecution(Base):
    __tablename__ = "recipe_executions"

    execution_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("migration_runs.result_id", ondelete="CASCADE"), nullable=False)
    recipe_id = Column(String(100), nullable=False)
    recipe_name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)
    duration_ms = Column(Integer, default=0, nullable=False)
    logs = Column(Text, nullable=True)


class DBBuildResult(Base):
    __tablename__ = "build_results"

    build_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("migration_runs.result_id", ondelete="CASCADE"), nullable=False)
    success = Column(Boolean, nullable=False)
    command = Column(String(512), nullable=False)
    output = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class DBTestResult(Base):
    __tablename__ = "test_results"

    test_run_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("migration_runs.result_id", ondelete="CASCADE"), nullable=False)
    success = Column(Boolean, nullable=False)
    command = Column(String(512), nullable=False)
    total_tests = Column(Integer, default=0, nullable=False)
    passed_tests = Column(Integer, default=0, nullable=False)
    failed_tests = Column(Integer, default=0, nullable=False)
    output = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class DBMigrationError(Base):
    __tablename__ = "migration_errors"

    error_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("migration_runs.result_id", ondelete="CASCADE"), nullable=False)
    stage = Column(String(100), nullable=False)
    error_type = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    traceback = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class DBMigrationReport(Base):
    __tablename__ = "migration_reports"

    report_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("migration_runs.result_id", ondelete="CASCADE"), nullable=False)
    risk_level = Column(String(50), nullable=False)
    summary = Column(Text, nullable=True)
    full_report_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
